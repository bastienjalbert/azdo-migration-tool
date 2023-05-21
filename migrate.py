import subprocess
import requests
from pathlib import Path
import shutil
import os
import json
from argparse import ArgumentParser
import tarfile

#####
# Tool to simplify Azure DevOps Artifact migration to Github
#####
__author__ = "Bastien Enjalbert"
__copyright__ = "Copyright 2023, Bastien Enjalbert"
__license__ = "MIT"
__version__ = "1.0.0"

TMP_PATH = "./tmp"


def build_parser():
    parser = ArgumentParser()
    # Required arguments
    required_args = parser.add_argument_group('required arguments')
    required_args.add_argument("--azorg", dest="azorg",
                               help="azure devops organization name",
                               default=None, required=True)
    required_args.add_argument("--azfeedId", dest="azfeedId",
                               help="azure devops feed id",
                               default=None, required=True)
    required_args.add_argument("--type", dest="type",
                               help="feed type (npm, ...)",
                               default=None, required=True)
    # Optional arguments
    parser.add_argument("--verbose", dest="verbose",
                        help="enable verbose mode",
                        default=True, action='store_true')
    parser.add_argument("--publish", dest="publish",
                        help="enable publish to github repo, otherwhise only download. disabled by default",
                        default=False, action='store_true')
    parser.add_argument("--slow", dest="slow",
                        help="if true, you'll be asked to continue for each package when publishing",
                        default=False, action='store_true')
    parser.add_argument("--first", dest="first",
                        help="do the migration (publish) of the first AzDO package only. Usefull for testing purpose",
                        default=False, action='store_true')
    parser.add_argument("--GITHUB_TOKEN", dest="GITHUB_TOKEN",
                        help="Github Token (to publish). Mandatory if you enable publish",
                        default=None)
    parser.add_argument("--azPAT", dest="azPAT",
                        help="azure devops PAT (readonly on artifact)",
                        default=None)
    parser.add_argument("--githubPAT", dest="githubPAT",
                        help="github PAT (packages write)",
                        default=None)
    parser.add_argument("--githuborg", dest="githuborg",
                        help="github organization name",
                        default=None)
    parser.add_argument("--githubfeedId", dest="githubfeedId",
                        help="github feed id",
                        default=None)

    return parser


packages_to_copy = [
    # id
    # normalizedName,
    # name,
    # versions
]


def main(config):
    # Cleanup temporary folder
    if os.path.exists(TMP_PATH) and os.path.isdir(TMP_PATH):
        shutil.rmtree(TMP_PATH)

    # List all packages from feed
    packages = get_azure_packages(config['azorg'], config['azfeedId'], config['azPAT'])

    total_number_of_package_downloaded = 0

    print("== Number of package to analyze in the AzDO feed " + str(len(packages)))

    # We're going to fetch all packages versions and provenances to identify only our organizational package
    for package in packages:
        if 'custom' not in package['normalizedName']:
            continue
        # fetch all version of the current packages
        versions = get_azure_package_version(config['azorg'], config['azfeedId'], package['id'], config['azPAT'])
        versions_to_copy = []
        for version in versions:
            # sourceChain attribute contains sources of the package
            # if the package were fetched from upstream
            # so if it's empty, the package in not publish to public registry (ie npmjs.org, ...)
            if len(version['sourceChain']) == 0:
                versions_to_copy.append(version)
                total_number_of_package_downloaded += 1
                # download the package (version) and untar
                if config['type'] == 'npm':
                    download_azure_npm_package_version(
                        config['azorg'], config['azfeedId'], package['name'],
                        version['version'], config['azPAT'], untar=True
                    )

        # if some version has matched, we need to copy this packages (and all his version)
        if len(versions_to_copy) != 0:
            packages_to_copy.append({
                'id': package['id'],
                'name': package['name'],
                'normalizedName': package['normalizedName'],
                'versions': versions_to_copy
            })

    print("== Number of package downloaded in the AzDO feed " + str(len(packages_to_copy)))
    print("== Number of package downloaded (w/ versions) in the AzDO feed " + str(total_number_of_package_downloaded))

    # Publish packages to github
    if "publish" in config:
        if "githuborg" not in config:
            print("You have to specify a github organization to continue")
            print("Try again by add the argument --githuborg [ORG_NAME]")
            exit(1)
        print('========================================')
        print('== These packages will be publish to github : [', end='')
        for p in packages_to_copy: print(p['normalizedName'] + ", ", end='')
        print(']')
        answer = input("Continue ? [Y/n]")
        if answer.lower() in ["y", "yes"]:
            publish_to_github(packages_to_copy, config['type'], config['githuborg'], config['githubPAT'],
                              config['slow'], config['first'])
        elif answer.lower() in ["n", "no"]:
            exit(0)
        else:
            publish_to_github(packages_to_copy, config['type'], config['githuborg'], config['githubPAT'],
                              config['slow'], config['first'])
    else:
        print('== These packages has been downloaded from Azure DevOps : ')
        for p in packages_to_copy:
            versions = [str(x['version']) for x in p['versions']]
            print(p['normalizedName'] + ", with version(s) : [" + ', '.join(versions) + "]")


def publish_to_github(packages, type, org_name, token, slow, first):
    """
    Publish a package to github registry using npm command
    :param packages: list of package to publish
    :param type: type of package ['npm', ...]
    :param org_name: github organization name
    :param token: github PAT token
    :param slow: if True, an user interaction is mandatory after each package publish
    :param first: if True, only publish the first package (and his versions), otherwise publish all packages / verions
    :return:
    """
    if type == 'npm':
        print("== Before continue, please ensure your ~/.npmrc has these 2 lines : ")
        print("             registry=https://npm.pkg.github.com/ORGA-NAME")
        print("             //npm.pkg.github.com/:_authToken=${GITHUB_TOKEN}")
        input("Press Enter to continue when you are ready...")
        for p in packages:
            print()
            published_version = []
            for v in p['versions']:
                package_folder = TMP_PATH + "/" + p['name'] + "/" + v['version'] + "/package/"
                package_json_path = package_folder + "package.json"
                github_npm_package_json_update(package_json_path, p['name'], org_name)
                f_out = open(package_folder + "../stdout.txt", "w")
                f_err = open(package_folder + "../stderr.txt", "w")
                try:
                    subprocess.check_call('GITHUB_TOKEN="' + token + '"  npm publish ' + package_folder,
                                          shell=True, stdout=f_out, stderr=f_err)
                    published_version.append(v['version'])
                except Exception:
                    print("== An error occur while publishing package " + p['name'] + " version " + v['version'])
                    print("== More information in " + package_folder + "../publish_npm_output.txt file")
            new_name = "@" + org_name + "/" + p['name']
            if len(published_version) != 0:
                print("== Package published : " + p['name'] + " (new name is " + new_name + ") with version(s) : ["
                      + ', '.join(str(x) for x in published_version) + "]")
            if first:
                exit(0)
            if slow:
                input("Press Enter to pass to the next package...")


def github_npm_package_json_update(pckg_file_path, pckg_name, org_name):
    """
    Update the package.json package to match github requirements
    See more https://tinyurl.com/pckgjsongithubdoc
    """
    # Rename the package. It need the organization prefix. See more here : https://github.com/sindresorhus/np/issues/489#issuecomment-1043057816
    with open(pckg_file_path, 'r+') as f:
        data = json.load(f)
        data['name'] = "@" + org_name + "/" + pckg_name
        f.seek(0)  # <--- should reset file position to the beginning.
        json.dump(data, f, indent=4)
        f.truncate()  # remove remaining part
    # Set the registry configuration
    with open(pckg_file_path, 'r+') as f:
        data = json.load(f)
        data['publishConfig'] = {"registry": "https://npm.pkg.github.com/" + org_name}
        f.seek(0)  # <--- should reset file position to the beginning.
        json.dump(data, f, indent=4)
        f.truncate()  # remove remaining part


def get_azure_packages(organization, feed_id, PAT):
    """
    Fetch all packages from an organization feed in Azure DevOps
    :param organization: name
    :param feed_id: name
    :param PAT: Azure DevOps PAT to read packages
    :return: raw json results
    """
    return requests.get(
        'https://feeds.dev.azure.com/' + organization + '/_apis/packaging/Feeds/' + feed_id + '/packages?api-version=7.0',
        auth=("", PAT)
    ).json()['value']


def get_azure_package_version(organization, feed_id, package_id, PAT):
    """
    :param organization: name
    :param feed_id: name
    :param package_id: internal AzDO ID
    :param PAT: Azure DevOps PAT to read packages
    :return: raw json results
    """
    return requests.get(
        'https://feeds.dev.azure.com/' + organization + '/_apis/packaging/Feeds/' + feed_id + '/Packages/' + package_id
        + '/versions?api-version=7.0', auth=("", PAT)
    ).json()['value']


def download_azure_npm_package_version(organization, feed_id, package_name, package_version, PAT, untar):
    """
    Download a npm package (specific version) from Azure DevOps
    :param organization: name
    :param feed_id: name
    :param package_name: name (not normalized name)
    :param package_version: version (not AzDO internal, ie 1.0.1)
    :param PAT:
    :param untar: if True, the package will be untar automatically; otherwise the archive will be download and save "as is"
    :return: output file name or the directory path if untar is True
    """
    Path(os.path.join(TMP_PATH, package_name)).mkdir(parents=True, exist_ok=True)
    pathname = TMP_PATH + "/" + package_name + "/"
    filename = pathname + package_version
    with requests.get(
            'https://pkgs.dev.azure.com/' + organization + '/_apis/packaging/feeds/' + feed_id + '/npm/packages/' + package_name +
            '/versions/' + package_version + '/content?api-version=7.0',
            auth=('', PAT),
            stream=True,
            headers={'Content-type': 'application/octet-stream'}
    ) as r:
        if untar:
            tar = tarfile.open(fileobj=r.raw)
            tar.extractall(path=filename)
            tar.close()
        else:
            with open(filename, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
    return filename


if __name__ == "__main__":
    parser = build_parser()
    options = parser.parse_args()

    config = {}
    if options.azorg:
        config['azorg'] = options.azorg
    if options.azfeedId:
        config['azfeedId'] = options.azfeedId
    if options.githuborg:
        config['githuborg'] = options.githuborg
    if options.githubfeedId:
        config['githubfeedId'] = options.githubfeedId
    if options.azPAT:
        config['azPAT'] = options.azPAT
    if "azPAT" in os.environ:
        config['azPAT'] = os.environ['azPAT']
    if options.githubPAT:
        config['githubPAT'] = options.githubPAT
    if "githubPAT" in os.environ:
        config['githubPAT'] = os.environ['githubPAT']
    if options.type:
        config['type'] = options.type
    config['publish'] = options.publish
    config['verbose'] = options.verbose
    config['slow'] = options.slow
    config['first'] = options.first

    if not config['azPAT']:
        print("Need a valid Azure DevOps PAT (readonly on packages)")
        exit()

    main(config=config)
