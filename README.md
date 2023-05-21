# Migration tool for Azure DevOps Artifact to Github registry

## Installation

Create a virtual environment (python 3.8+) and load it
```bash
python -m venv ./venv
source ./venv/bin/activate
```
Install dependencies 

```bash
pip install -r requirements.txt
```

Setup .npmrc configuration. *~/.npmrc* file should have these lines.
Replace **ORGA-NAME** with your Github organization. The GITHUB_TOKEN will
be pass automatically
```bash
registry=https://npm.pkg.github.com/ORGA-NAME
//npm.pkg.github.com/:_authToken=${GITHUB_TOKEN}
```

## Usage

You need to pass some required arguments such as *azorg* or *type*.

To see the full list run the help :
```bash
python migrate.py --help
```

You'll need at least an Azure DevOps PAT to read packages. 
You can pass the PAT with an environment variable (named azPAT) or with an argument --azPAT.

In the same way, if you want to publish packages to Github, you will need to generate a write packages PAT.
You can pass the PAT with an environment variable (named githubPAT) or with an argument --githubPAT

## Examples 

**For these example, 'azPAT' and 'githubPAT' environment variable has been defined with PATs.**

Only download packages without publish to github (usefull to prepare migration) :
```bash
python migrate.py --azorg [org] --azfeedId [feed] --githuborg [org-hub] --type npm
```

Download packages (w/ all versions) and publish them to github. Ask for a confirmation 
 after each publish, show verbose output and :
```bash
python migrate.py --azorg [org] --azfeedId [feed] --githuborg [org-hub] --type npm --publish --verbose --slow
```

Download the first package from AzDO Arfifact feed and publish it to github :
```bash
python migrate.py --azorg [org] --azfeedId [feed] --githuborg [org-hub] --type npm --publish --first
```