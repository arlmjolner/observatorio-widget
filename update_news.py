import json, urllib.request, xml.etree.ElementTree as ET, re, html, datetime, email.utils
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urlparse

BASE="https://news.google.com/rss"
PARAM="?hl=es&gl=ES&ceid=ES:es"
TOPICS={
    "Portada":BASE+PARAM,
    "Mundo":BASE+"/headlines/section/topic/WORLD"+PARAM,
    "Economía":BASE+"/headlines/section/topic/BUSINESS"+PARAM,
    "Tecnología":BASE+"/headlines/section/topic/TECHNOLOGY"+PARAM,
    "Ciencia":BASE+"/headlines/section/topic/SCIENCE"+PARAM,
    "Salud":BASE+"/headlines/section/topic/HEALTH"+PARAM,
    "OKDIARIO":"https://okdiario.com/feed",
    "Libertad Digital":BASE+"/search?q="+quote("site:libertaddigital.com when:3d")+"&hl=es&gl=ES&ceid=ES:es",
    "La Gaceta":BASE+"/search?q="+quote("site:gaceta.es when:3d")+"&hl=es&gl=ES&ceid=ES:es",
    "Público":BASE+"/search?q="+quote("site:publico.es when:3d")+"&hl=es&gl=ES&ceid=ES:es",
    "El Salto":"https://www.elsaltodiario.com/feed",
    "Mundo Obrero":BASE+"/search?q="+quote("site:mundoobrero.es when:7d")+"&hl=es&gl=ES&ceid=ES:es",
    "BBC News Mundo":"https://feeds.bbci.co.uk/mundo/rss.xml",
    "La Vanguardia":"https://www.lavanguardia.com/rss/home.xml",
    "elDiario.es":"https://www.eldiario.es/rss/",
    "Cadena SER":BASE+"/search?q="+quote("site:cadenaser.com when:3d")+ "&hl=es&gl=ES&ceid=ES:es",
    "EL PAÍS":"https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
    "The New York Times":"https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"
}
NS={"media":"http://search.yahoo.com/mrss/","content":"http://purl.org/rss/1.0/modules/content/"}
# Editorial tendency is a broad, contestable description of the outlet, not the article.
# Labels are intentionally descriptive rather than declaring every article partisan.
ALIGNMENTS={
"BBC News Mundo":"Sin clasificación","La Vanguardia":"Centro","elDiario.es":"Izquierda",
"Cadena SER":"Centroizquierda","EL PAÍS":"Centroizquierda","The New York Times":"Centroizquierda",
"OKDIARIO":"Derecha","Libertad Digital":"Derecha","La Gaceta":"Derecha radical",
"Público":"Izquierda","El Salto":"Izquierda alternativa","Mundo Obrero":"Izquierda comunista"
}

def clean(s):
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]*>"," ",s or ""))).strip()
def get_image(item):
    for el in item.iter():
        if el.tag in ("{http://search.yahoo.com/mrss/}content","{http://search.yahoo.com/mrss/}thumbnail","enclosure"):
            url=el.get("url","")
            if url.startswith("https://") and (el.tag!="enclosure" or el.get("type","image/").startswith("image/")):
                return url
    for tag in ("description","{http://purl.org/rss/1.0/modules/content/}encoded"):
        raw=item.findtext(tag,"")
        match=re.search(r'<img[^>]+src=["\x27]([^"\x27]+)',raw,re.I)
        if match and match.group(1).startswith("https://"):
            return html.unescape(match.group(1))
    return ""
def collect(item,label):
    def value(name):return (item.findtext(name,"") or "").strip()
    source=item.find("source")
    title=clean(value("title"))
    url=value("link")
    image=get_image(item)
    date=value("pubDate") or value("{http://purl.org/dc/elements/1.1/}date")
    try: date=email.utils.parsedate_to_datetime(date).isoformat()
    except Exception: date=""
    summary=clean(value("description"))
    return {"title":title,"description":summary[:320],"alignment":ALIGNMENTS.get(label,"Sin clasificación"),"source":label if label not in ("Portada","Mundo","Economía","Tecnología","Ciencia","Salud") else (source.text if source is not None else "Google News"),"url":url,"image":image,"date":date}
def load(pair):
    label,url=pair
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; ObservatorioNews/1.0)","Accept":"application/rss+xml, application/xml, text/xml, */*"})
        with urllib.request.urlopen(req,timeout=18) as response:raw=response.read(3000000)
        root=ET.fromstring(raw)
        nodes=root.findall("./channel/item")
        if not nodes: nodes=root.findall("{http://www.w3.org/2005/Atom}entry")
        stories=[collect(x,label) for x in nodes[:30]]
        stories=[x for x in stories if x["title"] and x["url"].startswith("https://")]
        print(label,len(stories),"images",sum(bool(x["image"]) for x in stories),flush=True)
        return label,stories
    except Exception as error:
        print(label,"FAILED:",error,flush=True)
        return label,[]
with ThreadPoolExecutor(max_workers=8) as executor:
    result=dict(executor.map(load,TOPICS.items()))
if not any(result.values()):
    raise SystemExit("All feeds failed; retaining previous news")
# Combine direct publisher RSS and Google News into one chronologically sorted front page.
# Keep source tabs intact and remove cross-feed duplicates by URL / normalized title.
publishers=("BBC News Mundo","La Vanguardia","elDiario.es","Cadena SER","EL PAÍS","The New York Times","OKDIARIO","Libertad Digital","La Gaceta","Público","El Salto","Mundo Obrero")
merged=[]
seen=set()
for label in ("Portada",)+publishers:
    for story in result.get(label,[]):
        key=re.sub(r"[^a-z0-9]+","",story["title"].casefold())
        key=key[:110] or story["url"].split("?")[0]
        if key in seen:continue
        seen.add(key)
        merged.append(story)
def sort_date(story):
    try:return datetime.datetime.fromisoformat(story["date"]).timestamp()
    except (ValueError, TypeError, KeyError):return 0
merged.sort(key=sort_date,reverse=True)
result["Últimas noticias"]=merged[:150]
print("Combined front page:",len(result["Últimas noticias"]),flush=True)
with open("news.json","w",encoding="utf-8") as output:
    json.dump({"updated":datetime.datetime.now(datetime.timezone.utc).isoformat(),"categories":result},output,ensure_ascii=False)
