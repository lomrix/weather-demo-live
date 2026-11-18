"""Generate the reviewed Koigen card and optionally discover traffic notices."""
import argparse
from datetime import datetime, timezone
import json
import re
import time
from html import escape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

from pathlib import Path

OUT = Path(__file__).resolve().parent / 'out'
AGENT = 'HamarAccessLabCourseDemo'
ROBOTS = 'https://www.hamar.kommune.no/robots.txt'

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Main(HTMLParser):
    def __init__(self, body):
        super().__init__()
        self.active = False
        self.text = []
        self.links = []
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        if tag == "main":
            self.active = True
        if self.active and tag == "a":
            self.links.append(dict(attrs).get("href") or "")

    def handle_endtag(self, tag):
        if tag == "main":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.text.append(data)




INDEX = "https://www.hamar.kommune.no/veger-og-gater/trafikkmeldinger/"
KOIGEN = INDEX + "sjoledning-skal-pa-plass-mellom-koigen-og-tjuvholmen"
GASBU = INDEX + "gasbuvegen-stengt-for-gjennomkjoring"
CONTACT = "https://www.hamar.kommune.no/kontakt-oss-her"
CASE = {
    "id": "koigen-sjoledning",
    "title": "Gangstien ved Koigen legges om",
    "location": "Langs Mjøsa ved Koigen avløpspumpestasjon",
    "impact": "Gangstien stenges under arbeidet. Alternativ gangvei blir skiltet.",
    "applies_to": ["pedestrians"],
    "pedestrian_status": "closure_announced",
    "start_date": None,
    "end_date": None,
    "source_url": KOIGEN,
    "map_segment": None,
}


def discover_links(html):
    links = {}
    for href in Main(html).links:
        url = urlsplit(urljoin(INDEX, href))
        if (url.scheme, url.netloc) != ("https", "www.hamar.kommune.no"):
            continue
        path = url.path.rstrip("/")
        slug = path.removeprefix(urlsplit(INDEX).path)
        if not slug or "/" in slug or slug == path:
            continue
        links[urljoin(INDEX, slug)] = None
    return list(links)


def fetch_page(url):
    request = Request(url, headers={"User-Agent": AGENT})
    with build_opener(NoRedirect()).open(request, timeout=12) as response:
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError("Siden overstiger størrelsesgrensen")
        return data.decode(response.headers.get_content_charset() or "utf-8")


def read_koigen(html):
    text = " ".join(" ".join(Main(html).text).split())
    publication = re.search(r"Publisert/sist endret:\s*(\d{2}\.\d{2}\.\d{4})", text)
    evidence = re.search(
        r"Mens byggingen av nytt ledningsnett fra avløpspumpestasjon[^.]+"
        r"vil gangstien langs Mjøsa bli stengt, og omlegging av gangstien skal være skiltet\.",
        text, re.IGNORECASE,
    )
    if not publication or not evidence:
        raise ValueError("Koigen-artikkelen har endret seg. Kontroller kilden før kortet oppdateres.")
    return {
        **CASE,
        "published_or_updated": publication[1],
        "evidence": evidence[0],
        "mode": "live",
    }


class ArticleHeading(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.in_heading = False
        self.parts = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "h1" and not self.parts:
            self.in_heading = True

    def handle_endtag(self, tag):
        if tag == "h1":
            self.in_heading = False

    def handle_data(self, data):
        if self.in_heading:
            self.parts.append(data)


def read_article_title(html):
    return " ".join("".join(ArticleHeading(html).parts).split())


def read_unverified(html, url, title):
    text = " ".join(" ".join(Main(html).text).split())
    date = re.search(r"Publisert/sist endret:\s*(\d{2}\.\d{2}\.\d{4})", text)
    gasbu = url == GASBU and "mellom Ingeberg og Korslund" in text
    return {
        "id": "gasbuvegen-utbedring" if url == GASBU else urlsplit(url).path.rsplit("/", 1)[-1],
        "title": title,
        "location": "Gåsbuvegen mellom Ingeberg og Korslund" if gasbu else "Se originalmeldingen.",
        "impact": "Ukjent. Sjekk originalmeldingen eller kontakt kommunen om gangadkomst.",
        "pedestrian_status": "needs_review",
        "published_or_updated": date[1] if date else "Ikke funnet",
        "source_url": url,
        "start_date": None,
        "end_date": None,
        "map_segment": None,
        "mode": "live",
    }


BASAR_URL = "https://www.hamar.kommune.no/nyhetsarkiv/velkommen-tilbake-til-8-meteren"
BASAR_EXCERPT = "Basarundergangen er stengt for biler, men du kan gå og sykle til Brygga kiosk og Koigen gjennom undergangen."


def basar_example():
    return {
        "id": "basarundergangen-arkiv",
        "title": "Basarundergangen (manuelt vurdert arkiveksempel)",
        "location": "Basarundergangen ved Koigen",
        "impact": "I arkivmeldingen kunne gående og syklende fortsatt passere.",
        "pedestrian_status": "passage_allowed_in_archive",
        "published_or_updated": "07.11.2025",
        "source_url": BASAR_URL,
        "start_date": None,
        "end_date": None,
        "map_segment": None,
        "mode": "archive",
        "evidence": BASAR_EXCERPT,
    }


def discover_live(export_koigen=False):
    policy = RobotFileParser()
    policy.parse(fetch_page(ROBOTS).splitlines())
    if not all(policy.can_fetch(AGENT, url) for url in (INDEX, KOIGEN)):
        raise ValueError("robots.txt tillater ikke henting av trafikkoversikten eller artikkelen")
    delay = max(5, policy.crawl_delay(AGENT) or 0)
    time.sleep(delay)
    links = discover_links(fetch_page(INDEX))
    if not links:
        raise ValueError("Fant ingen trafikkmeldinger. Kontroller sidestrukturen.")
    articles = []
    cases = []
    selected = links[:5]
    if KOIGEN in links and KOIGEN not in selected:
        selected[-1] = KOIGEN
    for url in selected:
        if not policy.can_fetch(AGENT, url):
            articles.append({"source_url": url, "error": "Blokkert av robots.txt"})
            continue
        time.sleep(delay)
        try:
            html = fetch_page(url)
            title = read_article_title(html)
            if not title:
                raise ValueError("Fant ingen artikkeltittel")
        except (OSError, ValueError, LookupError) as error:
            articles.append({"source_url": url, "error": str(error)})
            continue
        articles.append({"title": title, "source_url": url})
        case = read_unverified(html, url, title)
        if url == KOIGEN:
            if export_koigen:
                article_text = "\n".join(part.strip() for part in Main(html).text if part.strip())
                (OUT / "koigen-live-input.txt").write_text(article_text, encoding="utf-8")
            try:
                case = read_koigen(html)
            except ValueError as error:
                articles[-1]["card_error"] = str(error)
        cases.append(case)
    return links, articles, cases


BUS_URL = "https://innlandstrafikk.no/trafikkmeldinger/holdeplass-cc-hamar-retning-elverum-flyttes-midlertidig.63867.aspx"
BUS = {
    "title": "CC Hamar: holdeplassen mot Elverum flyttes",
    "title_en": "CC Hamar: Elverum-bound stop relocated",
    "location": "CC Hamar, retning Elverum",
    "location_en": "CC Hamar, towards Elverum",
    "impact": "Bruk den midlertidige holdeplassen ca. 100 meter nærmere Hamar sentrum. Se kartbildet hos Innlandstrafikk.",
    "impact_en": "The notice directs passengers to a temporary stop about 100 metres closer to central Hamar. See the map in the operator's notice.",
    "work_period": "Arbeidet var planlagt fra 5. november 2025 og skulle vare ca. 18 måneder. Ingen eksakt sluttdato oppgitt.",
    "work_period_en": "Work was scheduled to start on 5 November 2025 and last about 18 months. No exact end date was given.",
    "source_updated": "04.11.2025",
    "lines": "B21 B22 B24 B26 100 105 656 658 660 675 692 697",
}

EN_CASES = {
    "koigen-sjoledning": (
        "Footpath diversion at Koigen", "Along Lake Mjøsa near Koigen wastewater pumping station",
        "The footpath will close during construction. A diversion will be signposted.",
    ),
    "basarundergangen-arkiv": (
        "Basar underpass (historical example)", "Basar underpass near Koigen",
        "The archived notice says pedestrians and cyclists could still pass.",
    ),
}


def render_card(case, english=False):
    archived = case["mode"] == "archive"
    closure = case["pedestrian_status"] == "closure_announced"
    labels = (
        ("Where", "For pedestrians", "When", "Published or updated", "Data source", "Original Norwegian wording", "Read the source", "Contact Hamar municipality")
        if english else
        ("Hvor", "For deg som går", "Når", "Publisert/sist endret", "Datagrunnlag", "Ordlyd i kilden", "Les kommunens melding", "Kontakt Hamar kommune")
    )
    where, who, when, published, basis, wording, source, contact = labels
    title, location, impact = case["title"], case["location"], case["impact"]
    if english:
        title, location, impact = EN_CASES.get(case["id"], (title, "See the original notice.", "Pedestrian access is unknown."))
        if not archived and not closure:
            title, location, impact = case["title"], "See the original notice.", "Pedestrian access is unknown."
    if archived:
        date_label = "Historical example. Check current notices before travelling." if english else "Historisk eksempel. Sjekk dagens trafikkmeldinger."
    else:
        date_label = "The notice does not specify closure dates." if english and closure else "Dates for any pedestrian restrictions are unknown." if english else "Datoer for gangstengingen er ikke oppgitt." if closure else "Datoer for eventuelle gangrestriksjoner er ukjente."
    source_label = {
        "saved": "Saved demo example" if english else "Lagret demoeksempel",
        "archive": "Manually reviewed archive excerpt" if english else "Manuelt vurdert arkivutdrag",
        "live": ("Retrieved " if english else "Hentet ") + case.get("retrieved_at", ""),
    }[case["mode"]]
    evidence = escape(case.get("evidence", ""))
    source_note = f'<details><summary>{wording}</summary><p lang="nb">{evidence}</p></details>' if evidence else ""
    map_note = ""
    if closure and case["map_segment"] is None:
        map_note = "<p>Route simulation: the path segment has yet to be linked.</p>" if english else "<p>Rutesimulering: Gangsegmentet er ikke koblet til kartet ennå.</p>"
    return f"""<article><h2>{escape(title)}</h2>
<p><strong>{where}:</strong> {escape(location)}</p>
<p><strong>{who}:</strong> {escape(impact)}</p>
<p><strong>{when}:</strong> {date_label}</p>
<p><strong>{published}:</strong> {escape(case["published_or_updated"])}</p>
<p><strong>{basis}:</strong> {escape(source_label)}</p>
{source_note}
{map_note}
<p><a href="{escape(case["source_url"])}">{source}</a></p>
<p><a href="{CONTACT}">{contact}</a></p></article>"""


def render_bus(english):
    suffix = "_en" if english else ""
    label = "Manually reviewed bus notice. Check with Innlandstrafikk before travelling." if english else "Manuelt gjennomgått bussmelding. Sjekk Innlandstrafikk før du reiser."
    lines = "Affected lines" if english else "Berørte linjer"
    when = "When" if english else "Når"
    updated = "Source last updated" if english else "Kilden sist endret"
    link = "Read the bus notice and see the temporary stop" if english else "Les bussmeldingen og se den midlertidige holdeplassen"
    return f"""<article><h2>{escape(BUS["title" + suffix])}</h2>
<p>{escape(BUS["location" + suffix])}</p>
<p>{escape(BUS["impact" + suffix])}</p>
<p><strong>{lines}:</strong> {BUS["lines"]}</p>
<p><strong>{when}:</strong> {escape(BUS["work_period" + suffix])}</p>
<p><strong>{updated}:</strong> {BUS["source_updated"]}</p>
<p>{label}</p><p><a href="{BUS_URL}">{link}</a></p></article>"""


LANGUAGES = {"nb": "Norsk", "en": "English", "uk": "Українська"}
FLAGS = {
    "nb": '<path fill="#ba0c2f" d="M0 0h24v16H0z"/><path stroke="#fff" stroke-width="4" d="M8 0v16M0 8h24"/><path stroke="#00205b" stroke-width="2" d="M8 0v16M0 8h24"/>',
    "en": '<path fill="#012169" d="M0 0h24v16H0z"/><path stroke="#fff" stroke-width="3" d="m0 0 24 16M24 0 0 16"/><path stroke="#c8102e" d="m0 0 24 16M24 0 0 16"/><path stroke="#fff" stroke-width="5" d="M12 0v16M0 8h24"/><path stroke="#c8102e" stroke-width="3" d="M12 0v16M0 8h24"/>',
    "uk": '<path fill="#0057b7" d="M0 0h24v8H0z"/><path fill="#ffd700" d="M0 8h24v8H0z"/>',
}


def language_link(code, path):
    flag = f'<svg width="18" height="12" viewBox="0 0 24 16" aria-hidden="true">{FLAGS[code]}</svg>'
    return f'<a href="{path}" lang="{code}" hreflang="{code}">{flag} {LANGUAGES[code]}</a>'


UK_CASES = {
    "koigen-sjoledning": ("Обхід пішохідної доріжки біля Koigen", "Уздовж озера Mjøsa біля насосної станції Koigen",
                          "На час робіт доріжку закриють. Обхід позначать знаками."),
    "basarundergangen-arkiv": ("Підземний перехід Basar (архівний приклад)", "Підземний перехід біля Koigen",
                              "За архівним повідомленням, пішоходи й велосипедисти могли проходити."),
    "gasbuvegen-utbedring": ("Ремонт дороги Gåsbuvegen", "Дивіться повідомлення муніципалітету.",
                            "Невідомо, чи доступний прохід для пішоходів."),
}


def render_ukrainian_card(case):
    archive = case["mode"] == "archive"
    closure = case["pedestrian_status"] == "closure_announced"
    title, location, impact = case["title"], "Дивіться першоджерело.", "Доступ для пішоходів невідомий."
    if archive or closure or case["id"] == "gasbuvegen-utbedring":
        title, location, impact = UK_CASES.get(case["id"], (title, location, impact))
    when = "Дати закриття не вказано." if closure else "Дати можливих обмежень невідомі."
    if archive:
        when = "Архівний приклад. Перевірте актуальні повідомлення перед поїздкою."
    basis = {"archive": "Перевірений вручну архівний уривок", "saved": "Збережений приклад",
             "live": "Отримано " + case.get("retrieved_at", "")}[case["mode"]]
    quote = escape(case.get("evidence", ""))
    evidence = f'<details><summary>Оригінал норвезькою</summary><p lang="nb">{quote}</p></details>' if quote else ""
    return f"""<article><h2>{escape(title)}</h2>
<p><strong>Де:</strong> {escape(location)}</p>
<p><strong>Для пішоходів:</strong> {escape(impact)}</p>
<p><strong>Коли:</strong> {when}</p>
<p><strong>Опубліковано або оновлено:</strong> {escape(case["published_or_updated"])}</p>
<p><strong>Джерело даних:</strong> {escape(basis)}</p>{evidence}
<p><a href="{escape(case["source_url"])}">Читати оригінал</a></p>
<p><a href="{CONTACT}">Зв’язатися з муніципалітетом Hamar</a></p></article>"""


def render_ukrainian_bus():
    return f"""<article><h2>CC Hamar: тимчасове перенесення зупинки в напрямку Elverum</h2>
<p>За повідомленням перевізника, тимчасова зупинка приблизно на 100 метрів ближче до центру Hamar.</p>
<p><strong>Маршрути:</strong> {BUS["lines"]}</p>
<p><strong>Коли:</strong> Роботи планувалися з 5 листопада 2025 року приблизно на 18 місяців. Точну дату завершення не вказано.</p>
<p><strong>Джерело оновлено:</strong> {BUS["source_updated"]}</p>
<p>Повідомлення перевірено вручну. Перед поїздкою перевірте інформацію в Innlandstrafikk.</p>
<p><a href="{BUS_URL}">Повідомлення та карта тимчасової зупинки</a></p></article>"""


def write_page(filename, title, cases, include_bus=False):
    stem = filename.removesuffix(".html")
    pages = {"nb": filename, "en": f"{stem}-en.html", "uk": f"{stem}-uk.html"}
    titles = {
        "nb": title,
        "en": "Traffic notices and archive example" if include_bus else "Traffic notices for pedestrians in Hamar",
        "uk": "Дорожні повідомлення та архівний приклад" if include_bus else "Дорожні повідомлення для пішоходів у Hamar",
    }
    for language, output in pages.items():
        if language == "uk":
            cards = "".join(render_ukrainian_card(case) for case in cases)
            if include_bus:
                cards += render_ukrainian_bus()
        else:
            english = language == "en"
            cards = "".join(render_card(case, english) for case in cases)
            if include_bus:
                cards += render_bus(english)
        links = " · ".join(
            language_link(code, path)
            for code, path in pages.items() if code != language
        )
        if include_bus and (OUT / "ringgata-map.html").is_file():
            map_label = {
                "nb": "Åpne Ringgata-kartet (separat simulering)",
                "en": "Open the Ringgata map (separate simulation)",
                "uk": "Відкрити карту Ringgata (окрема симуляція)",
            }[language]
            cards += f'<p><a href="ringgata-map.html">{map_label}</a></p>'
        write_language_page(output, titles[language], cards, links, language)


def write_language_page(filename, title, cards, language_link, language):
    page = f"""<!doctype html>
<html lang="{language}"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{escape(title)}</title>
<style>
body {{ font: 1.1rem/1.55 system-ui; color: #172b2a; background: #f3f7f5; margin: 2rem 1rem; }}
main {{ max-width: 42rem; margin: auto; }}
article {{ padding: 1rem 1.5rem; margin-bottom: 1rem; background: white; border-radius: 1rem; }}
a {{ color: #005847; }}
</style>
<main><nav>{language_link}</nav><h1>{escape(title)}</h1>{cards}</main></html>
"""
    (OUT / filename).write_text(page, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Finn lenker i kommunens trafikkoversikt")
    parser.add_argument("--archive-example", action="store_true", help="Vis arkivtesten for Basarundergangen")
    parser.add_argument("--export-koigen", action="store_true", help="Lagre hovedinnholdet fra Koigen-siden")
    args = parser.parse_args()
    if args.export_koigen and not args.live:
        parser.error("--export-koigen krever --live")
    case = {**CASE, "published_or_updated": "29.10.2026", "mode": "saved"}
    cases = [case]
    OUT.mkdir(exist_ok=True)
    if args.live:
        run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        status_path = OUT / "traffic-live-status.json"
        status = {"attempted_at": run_at, "status": "in_progress"}
        status_path.write_text(json.dumps(status), encoding="utf-8")
        if args.export_koigen:
            (OUT / "koigen-live-input.txt").unlink(missing_ok=True)
        try:
            links, articles, cases = discover_live(export_koigen=args.export_koigen)
        except (OSError, ValueError, LookupError) as error:
            status.update(status="failed", error=str(error))
            status_path.write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")
            parser.exit(1, f"Live-henting feilet: {error}. Tidligere filer kan fortsatt ligge i out.\n")
        if args.export_koigen and not (OUT / "koigen-live-input.txt").is_file():
            status.update(status="partial", error="Koigen-teksten ble ikke hentet")
            status_path.write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")
            parser.exit(1, "Koigen-teksten ble ikke hentet.\n")
        for case in cases:
            case["retrieved_at"] = run_at
        for article in articles:
            article["retrieved_at"] = run_at
        OUT.mkdir(exist_ok=True)
        (OUT / "traffic-links.json").write_text(json.dumps(links, indent=2), encoding="utf-8")
        (OUT / "traffic-articles.json").write_text(
            json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Fant {len(links)} lenker. Sjekket opptil fem artikler:")
        for article in articles:
            print(f"- {article.get('title') or article['error']}")
            print(f"  {article['source_url']}")
            if "card_error" in article:
                print(f"  {article['card_error']}")
    if args.archive_example:
        archive_cases = [*cases, basar_example()]
        OUT.mkdir(exist_ok=True)
        write_page("traffic-archive-test.html", "Trafikkmeldinger og arkivtest", archive_cases, include_bus=True)
        print(OUT / "traffic-archive-test.html")
        if not args.live:
            return
    (OUT / "traffic-cases.json").write_text(
        json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_page("traffic.html", "Trafikkmeldinger for gående i Hamar", cases)
    for case in cases:
        if case["id"] == CASE["id"]:
            (OUT / "koigen.json").write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
            write_page("koigen.html", "Trafikkmelding fra Koigen", [case])
    if args.live:
        status["status"] = "partial" if any("error" in a or "card_error" in a for a in articles) else "ok"
        status_path.write_text(json.dumps(status), encoding="utf-8")
    print(f"Skrev {len(cases)} kort til {OUT / 'traffic.html'}")


if __name__ == "__main__":
    main()
