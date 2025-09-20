import time
import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import shutil
import sys

BASE_URL = 'https://ojs.aaai.org'
OUTPUT_ROOT = 'essay'

# 并行与下载参数（可按需调整）
MAX_WORKERS = 8          # 同时下载的最大并发数
DOWNLOAD_DELAY = 0.2     # 每个文件完成后的轻微延时，避免触发限流

def replaceIllegalStr(s):
    for ch in r':?/\\, .':
        s = s.replace(ch, '_')
    return s

def safe_print(obj):
    try:
        print(obj)
    except UnicodeEncodeError:
        try:
            text = str(obj) + "\n"
            sys.stdout.buffer.write(text.encode(sys.stdout.encoding or 'utf-8', errors='replace'))
        except Exception:
            # 最后兜底
            print(str(obj).encode('utf-8', errors='replace').decode('utf-8', errors='ignore'))

def getFile(session, url, title, dest_dir, referer=None):
    os.makedirs(dest_dir, exist_ok=True)
    filename = replaceIllegalStr(title) + '.pdf'
    dest = os.path.join(dest_dir, filename)
    try:
        print("Saving ->", dest.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore'))
    except Exception:
        print("Saving file (filename encoding issue)")
    try:
        # 针对下载请求单独补充必要的头以避免403
        dl_headers = {
            "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        }
        if referer:
            dl_headers["Referer"] = referer
        with session.get(url, headers=dl_headers, stream=True, timeout=60) as r:
            r.raise_for_status()
            total_bytes = int(r.headers.get('Content-Length', 0))
            desc = f"PDF: {title[:40]}" + ("..." if len(title) > 40 else "")
            with open(dest, 'wb') as f, tqdm(
                total=total_bytes if total_bytes > 0 else None,
                unit='B', unit_scale=True, unit_divisor=1024,
                desc=desc, leave=False, dynamic_ncols=True
            ) as pbar:
                for chunk in r.iter_content(chunk_size=1024 * 128):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))
        print("Downloaded")
    except Exception as e:
        print(f"Download error: {e}")
        raise
    return dest

def openAndDownload(url, title, dest_dirs):
    # 统一绝对化 URL（兼容相对链接）
    url = urljoin(BASE_URL, url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://ojs.aaai.org/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504, 429])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    # 统一为本 session 设置默认头，便于后续下载请求沿用
    session.headers.update(headers)
    try:
        resp = session.get(url, headers=headers, allow_redirects=True, timeout=15)
    except Exception as e:
        print(f"Request failed: {e}")
        return

    # 如果所有目标文件都已存在，则整体跳过
    filename_only = replaceIllegalStr(title) + '.pdf'
    if dest_dirs:
        all_exist = True
        for d in dest_dirs:
            if not os.path.exists(os.path.join(d, filename_only)):
                all_exist = False
                break
        if all_exist:
            print(f"{filename_only} already exists in all target folders, skipping.")
            return

    # 1. 如果直接是PDF
    if resp.headers.get('Content-Type', '').startswith('application/pdf'):
        primary_dir = dest_dirs[0] if dest_dirs else OUTPUT_ROOT
        os.makedirs(primary_dir, exist_ok=True)
        # 使用流式下载以显示速度，并显式携带 Referer
        dest = getFile(session, url, title, primary_dir, referer=BASE_URL)
        print("Downloaded (direct PDF)")
        # 复制到其他关键词目录
        for d in dest_dirs[1:]:
            os.makedirs(d, exist_ok=True)
            target = os.path.join(d, filename_only)
            if not os.path.exists(target):
                try:
                    shutil.copyfile(dest, target)
                except Exception as e:
                    print(f"Copy failed to {target}: {e}")
        if DOWNLOAD_DELAY:
            time.sleep(DOWNLOAD_DELAY)
        return

    # 2. 否则尝试查找PDF链接
    soup = BeautifulSoup(resp.text, 'lxml')
    pdf_link = soup.find('a', string='PDF')
    if not pdf_link or not pdf_link.get('href'):
        print(f"Warning: No PDF link found on {url}")
        return

    downloadUrl = urljoin(BASE_URL, pdf_link['href'])
    print("-> Downloading from:", downloadUrl)
    # 下载一次到主目录，再复制到其他目录
    primary_dir = dest_dirs[0] if dest_dirs else OUTPUT_ROOT
    dest_path = getFile(session, downloadUrl, title, primary_dir, referer=url)
    for d in dest_dirs[1:]:
        os.makedirs(d, exist_ok=True)
        target = os.path.join(d, filename_only)
        if not os.path.exists(target):
            try:
                shutil.copyfile(dest_path, target)
            except Exception as e:
                print(f"Copy failed to {target}: {e}")
    if DOWNLOAD_DELAY:
        time.sleep(DOWNLOAD_DELAY)  # 下载后轻微延时，防止被封

def main():
    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    header = {
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": "Mozilla/5.0"
    }

    # 直接在此处设置关键词，留空列表则全部下载（会放入 all 子文件夹）
    keywords = ['adversarial', 'diffusion', 'unpair', 'restoration', 'domain']
    # keywords = []
    keywords = [k.strip().lower() for k in keywords]

    for issue_num in range(627, 649):  # 包含648
        print(f"Processing issue {issue_num} ...")
        issue_url = f'https://ojs.aaai.org/index.php/AAAI/issue/view/{issue_num}'
        try:
            resp = requests.get(issue_url, headers=header)
            resp.raise_for_status()
        except Exception as e:
            print(f"Failed to fetch issue {issue_num}: {e}")
            continue

        soup = BeautifulSoup(resp.text, 'lxml')
        articles = soup.select('.obj_article_summary')
        records = []
        for art in articles:
            title = art.select_one('h3.title a').get_text(strip=True)
            # 新增：关键词过滤
            if keywords:
                title_lower = title.lower()
                matched = [kw for kw in keywords if kw in title_lower]
                if not matched:
                    continue
            else:
                matched = ['all']
            authors = art.select_one('.authors').get_text(strip=True)
            pages = art.select_one('.pages').get_text(strip=True)
            pdf_a = art.select_one('a.obj_galley_link.pdf')
            if pdf_a:
                pdf_link = pdf_a['href']
                filename = f"{title}"
                dest_dirs = [os.path.join(OUTPUT_ROOT, replaceIllegalStr(m)) for m in matched]
                records.append((filename, pdf_link, dest_dirs))

        df = pd.DataFrame([(fn, link, ';'.join(dirs)) for fn, link, dirs in records], columns=['filename','link','folders'])
        df.to_csv(f'essayList_{issue_num}.csv', index=False, encoding='utf-8-sig')
        safe_print(df.to_string(index=False))

        # 并行任务（存在判断在下载函数内部完成）
        tasks = [(filename, href, dest_dirs) for filename, href, dest_dirs in records]

        if not tasks:
            print(f"Issue {issue_num}: nothing to download.")
            continue

        # 并行下载
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(openAndDownload, href, filename, dest_dirs) for filename, href, dest_dirs in tasks]
            for f in tqdm(as_completed(futures), total=len(futures), desc=f"Downloading issue {issue_num}", unit="file"):
                try:
                    f.result()
                except Exception as e:
                    try:
                        tqdm.write(f"Download failed: {e}")
                    except Exception:
                        print(f"Download failed: {e}")

if __name__ == '__main__':
    main()
