import json, urllib.request, xml.etree.ElementTree as ET, re, html, datetime, email.utils
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

BASE="https://news.google.com/rss"
PARAM="?hl=es&gl=ES&ceid=ES:es"
TOPICS={"Portada":BASE+PARAM,"Mundo":BASE+"/headlines/section/topic/WORLD"+PARAM,"Economía":BASE+"/headlines/section/topic/BUSINESS"+PARAM,"Tecnología":BASE+"/headlines/section/topic/TECHNOLOGY"+PARAM,"Ciencia":BASE+"/headlines/section/topic/SCIENCE"+PARAM,"Salud":BASE+"/headlines/section/topic/HEALTH"+PARAM}
NS={"media":"http://search.yahoo.com/mrss/"}
def clean(s): return re.sub(r"\\s+"," ",html.unescape(re.sub(r"<[^>]*>"," ",s or ""))).strip()
def collect(item):
    def value(name): return item.findtext(name,default="").strip()
    title=clean(value("title"))
    desc=clean(value("description"))
    source=item.find("source")
    media=item.find("media:content",NS) or item.find("media:thumbnail",NS)
    enclosure=item.find("enclosure")
    image=(media.get("url") if media is not None else "") or (enclosure.get("url") if enclosure is not None else "")
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
