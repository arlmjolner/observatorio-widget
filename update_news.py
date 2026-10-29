import json, urllib.request, xml.etree.ElementTree as ET, re, html, datetime, email.utils
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

BASE="https://news.google.com/rss"
PARAM="?hl=es&gl=ES&ceid=ES:es"
TOPICS={"Portada":BASE+PARAM,"Mundo":BASE+"/headlines/section/topic/WORLD"+PARAM,"Economía":BASE+"/headlines/section/topic/BUSINESS"+PARAM,"Tecnología":BASE+"/headlines/section/topic/TECHNOLOGY"+PARAM,"Ciencia":BASE+"/headlines/section/topic/SCIENCE"+PARAM,"Salud":BASE+"/headlines/section/topic/HEALTH"+PARAM}
NS={"media":"http://search.yahoo.com/mrss/"}
def clean(s): return re.sub("\\s+"," ",html.unescape(re.sub("<[^>]*>"," ",s or ""))).strip()
def collect(item):
    def value(name): return item.findtext(name,default="").strip()
    title=clean(value("title"))
    desc=clean(value("description"))
    source=item.find("source")
    # Prefer a genuine image from the RSS item (RSS and Media RSS).
    image=""
    for node in (item.find("media:content", NS), item.find("media:thumbnail", NS), item.find("enclosure")):
        if node is not None and (node.get("url") or "").startswith("https://"):
            if node.tag == "enclosure" and node.get("type") and not node.get("type").startswith("image/"):
                continue
            image=node.get("url")
            break
    if not image:
        match=re.search("<img[^>]+src=[\"\u0027](https://[^\"\u0027]+)",value("description"),re.I)
        if match:image=html.unescape(match.group(1))
    if not image:
        # Google News often omits article images. Try Open Graph only when link
        # points directly to a publisher (not to news.google.com).
        from urllib.parse import urlparse
        link=value("link")
        if urlparse(link).hostname not in ("news.google.com", "www.google.com"):
            try:
                req=urllib.request.Request(link,headers={"User-Agent":"Mozilla/5.0"})
                with urllib.request.urlopen(req,timeout=5) as response:
                    if "text/html" in response.headers.get("Content-Type",""):
                        page=response.read(250000).decode("utf8","ignore")
                        for key in ("og:image","twitter:image"):
                            match=re.search("<meta[^>]*(?:property|name)=[\"\u0027]"+key+"[\"\u0027][^>]*content=[\"\u0027]([^\"\u0027]+)",page,re.I)
                            if match:image=html.unescape(match.group(1));break
            except Exception:
                pass
    try: date=email.utils.parsedate_to_datetime(value("pubDate")).isoformat()
    except Exception: date=""
    return {"title":title,"description":desc[:320],"source":source.text if source is not None else "Google News","url":value("link"),"image":image,"date":date}
def load(pair):
    label,url=pair
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; ObservatorioNews/1.0)"})
        with urllib.request.urlopen(req,timeout=20) as response: raw=response.read()
        root=ET.fromstring(raw)
        items=[collect(i) for i in root.findall("./channel/item")[:30]]
        items=[i for i in items if i["title"] and i["url"].startswith("https://")]
        print(label,len(items))
        return label,items
    except Exception as e:
        print(label,"FAILED",str(e))
        return label,[]
with ThreadPoolExecutor(max_workers=6) as pool:
    data=dict(pool.map(load,TOPICS.items()))
if not any(data.values()):
    raise SystemExit("No news returned; keeping the previous data")
with open("news.json","w",encoding="utf8") as f:
    json.dump({"updated":datetime.datetime.now(datetime.timezone.utc).isoformat(),"categories":data},f,ensure_ascii=False)
