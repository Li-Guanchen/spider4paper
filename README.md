# spider4paper
This Python script bulk-downloads AAAI papers. It filters by keyword (e.g., adversarial, diffusion), scrapes titles, authors and PDF links, exports a CSV index, then uses an multi-thread pool to fetch every PDF. Files are auto-renamed, de-duplicated and saved into keyword-based folders. 
