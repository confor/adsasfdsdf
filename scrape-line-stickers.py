import sys
import argparse
import requests
import os
from hashlib import md5
from bs4 import BeautifulSoup


def request_page(url: str, mobile=True):
    headers = {
        'Accept-Language': 'en-US,en:q=0.9',
    }

    if mobile:
        headers['User-Agent'] = 'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36 Edg/101.0.4951.64'
    else:
        headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36 Edg/101.0.1210.47'

    req = requests.get('https://store.line.me' + url, headers=headers, timeout=10)
    return (req.status_code, req.text)


def request_file(url: str) -> tuple[int, bytes]:
    req = requests.get(url, timeout=10)
    return (req.status_code, req.content)


def clean_str(text: str) -> str:
    return text.replace('\r', '').replace('\n', ' ').replace('\t', ' ').strip()


def clean_filename(text: str) -> str:
    # TODO include ascii range [0x00, 0x1F]
    for c in r'"#$*/\\|~^<>:@?':
        text = text.replace(c, '_')

    return text.strip()


def get_author(id: int):
    status, html = request_page(f'/stickershop/author/{id}/en')
    soup = BeautifulSoup(html, "html.parser")

    if status != 200:
        print("Error whilst downloading from line.me")
        print("HTTP status code not 200")

        html_error = soup.select_one('div.LyMain p[data-test="no-item-available-text"]')
        if html_error is not None:
            print(f"The author {id} was not found or has no published content")
        return

    # scrape packs from author's page
    # TODO run through all pages, currently line shows 36 items on the 1st page
    header = soup.select_one('body .LyMain [role="main"] h2').text
    main = soup.select_one('body .LyContents ul')

    # scrape sticker packs
    stickers = main.select('li a[href^="/stickershop/product/"]')
    stickerpacks = []
    for item in stickers:
        url = item.attrs['href']
        packid = url.split('/')[3]
        name = item.select_one('p[data-test="item-name"]').text
        stickerpacks.append({'url': url, 'packid': packid, 'name': name})

    # scrape emoticon packs
    emotes = main.select('li a[href^="/emojishop/product/"]')
    emotepacks = []
    for item in emotes:
        url = item.attrs['href']
        packid = url.split('/')[3]
        name = item.select_one('p[data-test="item-name"]').text
        emotepacks.append({'url': url, 'packid': packid, 'name': name})

    # show search results
    header = clean_str(header)
    print(f"Author: {header}")

    if len(stickerpacks) > 0:
        print(f"Available sticker packs:")

        for pack in stickerpacks:
            pack['name'] = clean_str(pack['name'])
            print(f"- {pack['packid']}: {pack['name']}")
    else:
        print("No available sticker packs")

    if len(emotepacks) > 0:
        print(f"Available emoticon packs:")

        for pack in emotepacks:
            pack['name'] = clean_str(pack['name'])
            print(f"- {pack['packid']}: {pack['name']}")
    else:
        print("No available emoticon packs")

    return


def get_pack(id: int) -> tuple[str, list]:
    status, html = request_page(f'/stickershop/product/{id}/en', False)
    soup = BeautifulSoup(html, "html.parser")

    if status != 200:
        print("Error whilst downloading from line.me")
        print("HTTP status code not 200")

    title = soup.select_one('.LyMain p[data-test="sticker-name-title"]').text
    stickers = soup.select('.LyMain section div div div ul.FnStickerList li.FnStickerPreviewItem')

    images = []

    for sticker in stickers:
        image = sticker.select_one('.FnImage span')
        style = image.attrs['style']
        # extract text between parentheses
        url = style[1 + style.find('(') : style.rfind(')')]
        images.append(url)

    return (clean_str(title), images)


def handle_author(id: int):
    get_author(id)


def handle_stickers(id: int, target_dir: str):
    print(f"Searching for sticker pack {id}")
    title, images = get_pack(id)
    print(f"Found sticker pack: {title}")
    print(f"Contains {len(images)} images, downloading...")

    # simple hash of the title to avoid collisions
    hash = md5(title.encode('utf-8')).hexdigest()
    sticker_dir = hash[:8] + ' - ' + clean_filename(title)

    os.mkdir(os.path.join(target_dir, sticker_dir))

    # write original sticker pack title
    file = open(os.path.join(target_dir, sticker_dir, "title.txt"), "w")
    file.write(title)
    file.close()

    # TODO use that file to check if the pack already exists

    # download and write each image
    i = 1
    for image in images:
        print('.', end='', flush=True)
        http_status, data = request_file(image)
        if http_status != 200:
            print(f"\nError in image #{i}: http status code not 200, skipping")
            continue

        target = os.path.join(target_dir, sticker_dir, f"{i:02}.png")  # are all stickers png? TODO check

        file = open(target, "wb")
        file.write(data)
        file.close()

        i = i + 1

    print("")

    return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--target", help="Folder where the sticker pack will be stored", type=str)
    parser.add_argument("-a", "--author", help="List all packs by author", type=int)
    parser.add_argument("-s", "--sticker", help="Download a specific sticker pack", type=int)
    # line emote pack ids are hexadecimal (they look like an md5 hash)
    parser.add_argument("-e", "--emote", help="Download an emoticon pack", type=str)
    args = parser.parse_args()

    if args.author:
        handle_author(args.author)
    elif args.sticker:
        if not args.target:
            print("Error: need a target directory to write the sticker pack")
            sys.exit(1)

        if not os.path.isdir(args.target):
            print("Error: given target is not a directory")
            sys.exit(1)

        handle_stickers(args.sticker, args.target)
    else:
        print("Error: unrecognized action")
        print("See: scrape.py --help")
        sys.exit(1)


if __name__ == "__main__":
    main()
