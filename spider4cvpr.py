import os
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from urllib.parse import urljoin
try:
    from tqdm import tqdm
except Exception:
    def tqdm(iterable=None, *args, **kwargs):
        return iterable if iterable is not None else []
from concurrent.futures import ThreadPoolExecutor, as_completed

def replace_illegal(s):
    # 替换所有可能导致路径问题的字符，包括空格、点、斜杠、反斜杠、冒号、星号、问号、引号、小于号、大于号、竖线等
    return re.sub(r'[\\/:*?"<>|\s\.]', '_', s)

def make_session():
    s = requests.Session()
    retries = Retry(total=5, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    s.mount('https://', HTTPAdapter(max_retries=retries))
    s.mount('http://', HTTPAdapter(max_retries=retries))
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://openaccess.thecvf.com/'
    })
    return s

def main():
    url = 'https://openaccess.thecvf.com/CVPR2025?day=all'
    base_url = 'https://openaccess.thecvf.com/'
    session = make_session()
    resp = session.get(url, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'lxml')
    content = soup.select_one('#content > dl')
    if not content:
        print('未找到论文列表')
        return
    # 阶段一：扫描并构建论文项列表
    children = content.find_all(['dt', 'dd'], recursive=False)
    items = []
    for idx, node in enumerate(children):
        if node.name != 'dt':
            continue
        a_tag = node.find('a')
        if not a_tag:
            continue
        text = (a_tag.get_text(strip=True) or '').strip()
        href = a_tag.get('href', '')
        # 仅保留真正标题（指向 html 详情页）
        if 'content/CVPR2025/html' not in href or text.lower() == 'pdf':
            continue
        title = text
        safe_title = replace_illegal(title)
        if not safe_title or safe_title.lower() == 'pdf':
            continue
        # 关联到对应的 dd（一般是 idx+2）提取 pdf 和 bibtex
        dd_idx = idx + 2
        pdf_url = None
        bibtex_text = ''
        if dd_idx < len(children) and children[dd_idx].name == 'dd':
            dd = children[dd_idx]
            pdf_a = dd.find('a', string=lambda s: isinstance(s, str) and s.lower() == 'pdf')
            if pdf_a and pdf_a.get('href'):
                pdf_url = urljoin(base_url, pdf_a['href'])
            inner = dd.select_one('div div')
            if inner:
                t = inner.get_text("\n", strip=True)
                if '@' in t:
                    bibtex_text = t
        items.append({
            'title': title,
            'safe_title': safe_title,
            'pdf_url': pdf_url,
            'bibtex_text': bibtex_text,
        })

    print(f"共发现论文：{len(items)} 篇")
    def download_one(item):
        title = item['title']
        safe_title = item['safe_title']
        folder = os.path.join('cvpr2025', safe_title)
        pdf_url = item['pdf_url']
        pdf_path = os.path.join(folder, f'{safe_title}.pdf')
        bibtex_text = item['bibtex_text']
        bib_path = os.path.join(folder, f'{safe_title}.txt')
        # 如果两个文件都已存在，整体跳过
        if (not pdf_url or os.path.exists(pdf_path)) and (not bibtex_text or os.path.exists(bib_path)):
            return f"跳过已存在: {safe_title}"
        os.makedirs(folder, exist_ok=True)
        msg = []
        # PDF
        if pdf_url and not os.path.exists(pdf_path):
            try:
                with session.get(pdf_url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    total_bytes = int(r.headers.get('Content-Length', 0))
                    with open(pdf_path, 'wb') as f, tqdm(
                        total=total_bytes if total_bytes > 0 else None,
                        unit='B', unit_scale=True, unit_divisor=1024,
                        desc=f"PDF: {safe_title[:40]}" + ("..." if len(safe_title) > 40 else ""),
                        leave=False,
                        dynamic_ncols=True,
                    ) as pbar:
                        for chunk in r.iter_content(chunk_size=1024 * 128):
                            if chunk:
                                f.write(chunk)
                                pbar.update(len(chunk))
            except Exception as e:
                msg.append(f"PDF下载失败: {e} -> {pdf_url}")
        elif os.path.exists(pdf_path):
            msg.append(f"PDF已存在，跳过: {safe_title}")
        # bibtex
        if bibtex_text and not os.path.exists(bib_path):
            try:
                with open(bib_path, 'w', encoding='utf-8') as f:
                    f.write(bibtex_text)
            except Exception as e:
                msg.append(f'bibtex保存失败: {e}')
        elif bibtex_text and os.path.exists(bib_path):
            msg.append(f"bibtex已存在，跳过: {safe_title}")
        return '\n'.join(msg) if msg else None

    max_workers = 10  # 可根据带宽和CPU调整
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(download_one, item) for item in items]
        for f in tqdm(as_completed(futures), total=len(futures), desc='下载进度', unit='paper'):
            result = f.result()
            if result:
                try:
                    tqdm.write(result)
                except Exception:
                    print(result)

if __name__ == '__main__':
    main()
