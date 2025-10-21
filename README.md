# Analysis of a PDF containing a Leistungsverzeichnis 

A Python-based tool for extracting unstructured data from a German construction tender PDF (Leistungsverzeichnis), transforming it in a structured format and showing insights on the respective tender. 

A Leistungsverzeichnis (bill of quantities or tender document) lists all construction tasks and materials for a project.

## Table of contents
- [Analysis of a PDF containing a Leistungsverzeichnis](#analysis-of-a-pdf-containing-a-leistungsverzeichnis)
  - [Table of contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Navigation](#navigation)
  - [Setup](#setup)
    - [Dependencies](#dependencies)
    - [Data](#data)
  - [Further Work](#further-work)
  - [Acknowledgements](#acknowledgements)
  - [Disclaimer](#disclaimer)

## Introduction
In this repository we analyze a PDF containing a tender for building a single-family house. It contains various main and sub-positions representing necessary work hours and goods necessary for building the house.

To extract data from the PDF and parse the unstructured text data into a structured form, we utilize the pdfplumber, regex, and pandas library.

This project represents only an initial Analysis and does not go in depth.

## Navigation

In the Notebook `data_analysis_LV.ipynb`, we utilize the MetaDataExtractor and PDFPostionExtractor class to extract data and show contents of the extracted data.

## Setup

### Dependencies

Built with Python 3.12.7 (lower versions are likely also compatible)

Create and activate virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies from requirements.txt file

```bash
pip install -r requirements.txt
```
### Data

For this project we utilized a PDF which represents a tender for a single-family house. The data can be found under the following link:

Source:
- https://www.wk-statik.de/app/download/13496174/LV+Rohbauarbeiten+Einfamilienhaus.pdf

The PDF is **not included** in this repository. It remains the property of WK Statik GmbH and is used here solely for educational purposes.

## Further Work

- Test robustness of created MetaDataExtractor and PDFPostionsExtractor class for other tenders for single-family households and adjust classes accordingly
- Gain more insights into the tender:
  - Calculate/Visualize total amount of work hours necessary (Also by task)
  - Calculate/Visualize total amount of raw materials necessary (Also by material type)
  - etc.
- Extract more insights from within each position description to extract more information in a structured way.

## Acknowledgements

- The sample tender document ("LV Rohbauarbeiten Einfamilienhaus") is provided by [WK Statik GmbH](https://www.wk-statik.de/).  
- Data extraction powered by [pdfplumber](https://github.com/jsvine/pdfplumber), [pandas](https://pandas.pydata.org/), and Python’s built-in `re` module.  

## Disclaimer

This project is intended for **educational purposes only**.  
The included or referenced PDF ("LV Rohbauarbeiten Einfamilienhaus") remains the property of its original author and publisher.  

The author of this repository does **not claim any ownership** over the document or its contents.