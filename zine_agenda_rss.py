#!/usr/bin/env python3
"""Gera um RSS 2.0 a partir da agenda paginada do Zine Cultural."""
from __future__ import annotations
import argparse, html, re, sys, threading, time
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urljoin, urlsplit, urlunsplit
import requests
from bs4 import BeautifulSoup

DEFAULT_URL = (
    "https://zinecultural.com/agenda-cultural/page/2?"
    "cidade%5B0%5D%5Bterm_id%5D=15&"
    "cidade%5B0%5D%5Bname%5D=Juiz%20de%20Fora&"
    "cidade%5B0%5D%5Bslug%5D=juiz-de-fora&"
    "cidade%5B0%5D%5Bterm_group%5D=0&"
    "cidade%5B0%5D%5Bterm_taxonomy_id%5D=15&"
    "cidade%5B0%5D%5Btaxonomy%5D=agenda_city&"
    "cidade%5B0%5D%5Bdescription%5D&"
    "cidade%5B0%5D%5Bparent%5D=0&"
    "cidade%5B0%5D%5Bcount%5D=2641&"
    "cidade%5B0%5D%5Bfilter%5D=raw"
)

def clean_url(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path, p.query, ""))

def plain_text(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip() if node else ""

def parse_page(html_text: str, page_url: str):
    soup = BeautifulSoup(html_text, "html.parser")
    events = []
    for anchor in soup.select("a.agenda-card-link"):
        card = anchor.select_one(".agenda-card") or anchor
        link = urljoin(page_url, anchor.get("href", "").strip())
        title = plain_text(card.select_one(".card-title-agenda"))
        if not title:
            image = card.select_one("img[alt]")
            title = image.get("alt", "").strip() if image else ""
        if not link or not title:
            continue
        date_text = plain_text(card.select_one(".card-date-container"))
        details = [plain_text(x) for x in card.select(".card-details > div")]
        details = [x for x in details if x]
        labels = [plain_text(x) for x in card.select(".card-labels-agenda span")]
        labels = [x for x in labels if x and x.casefold() != "hoje"]
        image_node = card.select_one(".card-image img") or card.select_one("img")
        image_url = urljoin(page_url, image_node.get("src", "")) if image_node and image_node.get("src") else ""
        events.append({"title": title, "link": clean_url(link), "date": date_text,
                       "details": details, "category": ", ".join(labels), "image": image_url})
    pagination = []
    for anchor in soup.select("a[href]"):
        href = urljoin(page_url, anchor.get("href", "").strip())
        text = plain_text(anchor)
        parts = urlsplit(href)
        if parts.netloc.lower() not in {"zinecultural.com", "www.zinecultural.com"}:
            continue
        if "/agenda-cultural" not in parts.path:
            continue
        if re.fullmatch(r"\d+", text) or re.search(r"anterior|pr[oó]ximo|previous|next|[«»]", text, re.I):
            pagination.append(clean_url(href))
    return events, pagination

def fetch_all(start_url: str, max_pages: int, delay: float):
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; ZineAgendaRSS/1.0; +https://zinecultural.com/)"})
    queue, visited, events_by_link, page_count = [clean_url(start_url)], set(), {}, 0
    while queue and page_count < max_pages:
        page_url = queue.pop(0)
        if page_url in visited:
            continue
        visited.add(page_url)
        try:
            response = session.get(page_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"Aviso: não foi possível ler {page_url}: {exc}", file=sys.stderr)
            continue
        page_count += 1
        page_events, next_pages = parse_page(response.text, response.url)
        for event in page_events:
            events_by_link.setdefault(event["link"], event)
        for next_url in next_pages:
            if next_url not in visited and next_url not in queue:
                queue.append(next_url)
        if delay:
            time.sleep(delay)
    if queue:
        print(f"Aviso: limite de {max_pages} páginas atingido; pode haver mais páginas.", file=sys.stderr)
    return list(events_by_link.values()), page_count

def make_rss(events, source_url: str, only_city: str | None):
    if only_city:
        target = only_city.casefold()
        events = [e for e in events if any(target in d.casefold() for d in e["details"])]
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Agenda cultural — Zine Cultural"
    ET.SubElement(channel, "link").text = source_url
    ET.SubElement(channel, "description").text = ("Eventos extraídos das páginas da agenda cultural do Zine Cultural. "
        "A data e os detalhes são os exibidos nos cartões da agenda.")
    ET.SubElement(channel, "language").text = "pt-BR"
    ET.SubElement(channel, "generator").text = "zine_agenda_rss.py"
    for event in events:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = event["title"]
        ET.SubElement(item, "link").text = event["link"]
        ET.SubElement(item, "guid", {"isPermaLink": "true"}).text = event["link"]
        facts = []
        if event["date"]:
            facts.append(f"<p><strong>Data:</strong> {html.escape(event['date'])}</p>")
        if event["category"]:
            facts.append(f"<p><strong>Categoria:</strong> {html.escape(event['category'])}</p>")
        if event["details"]:
            facts.append("<p>" + "<br />".join(html.escape(d) for d in event["details"]) + "</p>")
        if event["image"]:
            facts.append(f'<p><img src="{html.escape(event["image"], quote=True)}" alt="" /></p>')
        description = "".join(facts) or f'<p><a href="{html.escape(event["link"], quote=True)}">Ver evento</a></p>'
        ET.SubElement(item, "description").text = description
        if event["category"]:
            ET.SubElement(item, "category").text = event["category"]
    return ET.ElementTree(rss), len(events)

def rss_bytes(source_url: str, only_city: str | None, max_pages: int, delay: float) -> bytes:
    events, pages = fetch_all(source_url, max_pages, delay)
    tree, count = make_rss(events, source_url, only_city)
    print(f"Feed atualizado: {count} eventos; {pages} páginas consultadas.", file=sys.stderr)
    return ET.tostring(tree.getroot(), encoding="utf-8", xml_declaration=True)

def serve(args):
    cache = {"created": 0.0, "body": None}
    cache_lock = threading.Lock()
    class FeedHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?", 1)[0] not in {"/", "/feed.xml"}:
                self.send_error(404, "Use /feed.xml")
                return
            try:
                with cache_lock:
                    now = time.monotonic()
                    fresh = cache["body"] is not None and args.cache_seconds > 0 and now - cache["created"] < args.cache_seconds
                    if fresh:
                        body = cache["body"]
                    else:
                        body = rss_bytes(args.url, args.only_city, args.max_pages, args.delay)
                        cache.update(created=now, body=body)
            except Exception as exc:
                self.send_error(502, f"Falha ao atualizar a agenda: {exc}")
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, fmt, *args):
            print(f"[{self.log_date_time_string()}] {fmt % args}", file=sys.stderr)
    server = ThreadingHTTPServer((args.host, args.port), FeedHandler)
    print(f"Servindo RSS em http://{args.host}:{args.port}/feed.xml", file=sys.stderr)
    print("Para leitores RSS externos, hospede o servidor em um endereço público.", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

def main():
    parser = argparse.ArgumentParser(description="Converte a agenda paginada do Zine Cultural em RSS dinâmico.")
    parser.add_argument("--url", default=DEFAULT_URL, help="URL inicial da agenda, com os filtros desejados")
    parser.add_argument("--output", default="zine-agenda.xml", help="Arquivo RSS de saída no modo padrão")
    parser.add_argument("--only-city", help="Opcional: mantém cartões cujo texto de local contenha essa cidade")
    parser.add_argument("--max-pages", type=int, default=500, help="Limite de segurança para páginas percorridas")
    parser.add_argument("--delay", type=float, default=0.4, help="Pausa entre páginas, em segundos")
    parser.add_argument("--serve", action="store_true", help="Serve um RSS dinâmico em /feed.xml")
    parser.add_argument("--host", default="127.0.0.1", help="Interface de rede; use 0.0.0.0 para expor no servidor")
    parser.add_argument("--port", type=int, default=8080, help="Porta HTTP no modo --serve")
    parser.add_argument("--cache-seconds", type=int, default=300, help="Cache opcional do endpoint; use 0 para buscar em toda requisição")
    args = parser.parse_args()
    if args.serve:
        serve(args)
        return
    body = rss_bytes(args.url, args.only_city, args.max_pages, args.delay)
    with open(args.output, "wb") as output:
        output.write(body)
    root = ET.fromstring(body)
    print(f"RSS salvo em {args.output}: {len(root.findall('./channel/item'))} eventos.")

if __name__ == "__main__":
    main()
