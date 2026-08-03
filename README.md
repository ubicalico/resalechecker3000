A simple Flask web app for browsing, searching and filtering Singapore HDB
resale flat transactions from January 2017 onwards, using data from
[data.gov.sg](https://data.gov.sg/datasets/d_8b84c4ee58e3cfc0ece0d773c8ca6abc/view).

This is the updated version since they release this new dataset recently. You can view the website live here: [resale.hishamo.net](https://resale.hishamo.net)

## Libraries used

- **requests** — as the name implies, it is used to request for the resource from data.gov.sg 
- **pandas** — data cleaning, manipulation blah blah...
- **SQLAlchemy** — my uni taught me this so i used this LOL
- **Flask** — renders the web app (using Flask templates and HTML)
- **uWSGI** - entry point to Flask app
- **NGINX** - proxy between end user and uWSGI

## Setup

```
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

## Run

```
venv\Scripts\python app.py
```

Then open http://localhost:5000. On the very first run the app downloads the
full dataset and builds `hdb_resale.db` — this takes a minute
or two. After that, the process should be instant.

The dataset is periodically updated by the maintainer. To re-download the latest data at any time:

```
venv\Scripts\python data_loader.py
```


## Features

- Filter by every field: month range, town, flat type, storey range, flat
  model, block/street text search, floor area, resale price, lease commence
  year and remaining lease. (based on what provided by data.gov.sg)
- Header sorting
- Summary statistics (count, average/lowest/highest price, average price per
  sqm) for the current filter selection.

## Why 

"Why don't you run a node.js app?" This is meant to be lightweight and in a language that I fully comprehend. Have you ever tried debugging in JS?
"Why don't you add some visualisations?" Procrastination.
"data.gov.sg already has a data explorer, why I need to build my own with this?" You try that and let me know how that works out for you.

## Disclaimer
The project leverages information from data.gov.sg. Adhere to the [API limits](https://guide.data.gov.sg/developer-guide/api-overview/api-rate-limits) and use it responsibly. Do not let your AI agents poll it endlessly. 

Creating a publicly accessible on your local machine increases your surface area for malicious actors. Ensure you have the correct firewall configuration before running and exposing this application from your local machine. The above scripts is applicable to a Windows environment. Code changes may be necessary for other OS-es. Use the "deploy-fork" branch if you want to deploy it to your own VM instance. 
