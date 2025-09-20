# spider4paper

A Python script for bulk-downloading AAAI papers with keyword filtering and automated organization.

## Description

This Python script bulk-downloads AAAI papers. It filters by keyword (e.g., adversarial, diffusion), scrapes titles, authors and PDF links, exports a CSV index, then uses a multi-thread pool to fetch every PDF. Files are auto-renamed, de-duplicated and saved into keyword-based folders.

## Features

- **Keyword Filtering**: Filter papers by specific keywords
- **Metadata Scraping**: Extract titles, authors, and PDF links
- **CSV Export**: Generate an index of scraped papers
- **Multi-threaded Downloads**: Efficient parallel PDF downloading
- **Auto-organization**: Automatic file renaming and folder organization
- **Deduplication**: Prevent duplicate downloads

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Li-Guanchen/spider4paper.git
cd spider4paper
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Requirements

- Python 3.7+
- Dependencies listed in `requirements.txt`:
  - requests: For HTTP requests and PDF downloads
  - beautifulsoup4: For web scraping and HTML parsing
  - pandas: For CSV data handling and export
  - lxml: For fast XML/HTML parsing

## Usage

```bash
python spider4paper.py --keyword "adversarial" --output-dir "./papers"
```

## Output Structure

```
papers/
├── adversarial/
│   ├── paper1.pdf
│   ├── paper2.pdf
│   └── ...
├── index.csv
└── ...
```
