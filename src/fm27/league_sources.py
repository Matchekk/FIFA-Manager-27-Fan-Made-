"""Strict current-season league membership evidence, independent of player rosters."""
import re
from urllib.parse import urlsplit
from bs4 import BeautifulSoup


def parse_league_members(html, competition, season=2026):
    if not isinstance(season, int) or not 1900 <= season <= 2099 or not re.fullmatch(r'[A-Z0-9]+', competition):
        raise ValueError('Invalid league source identity')
    soup = BeautifulSoup(html, 'html.parser')
    canonical = soup.find('link', rel='canonical')
    url = urlsplit(canonical.get('href', '') if canonical else '')
    if (url.scheme != 'https' or url.hostname != 'www.transfermarkt.de'
            or not re.search(r'/startseite/wettbewerb/' + re.escape(competition) + r'(?:/|$)', url.path)):
        raise ValueError('Wrong canonical competition')
    selected = soup.select('select[name="saison_id"] option[selected]')
    if len(selected) != 1 or selected[0].get('value') != str(season):
        raise ValueError('Wrong or ambiguous league season')
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    if f'{season % 100:02}/{(season+1) % 100:02}' not in title:
        raise ValueError('League title does not confirm requested season')
    tables = [table for table in soup.select('table.items') if table.find('thead')
              and {'Verein','Kader'} <= {cell.get_text(' ',strip=True) for cell in table.find('thead').find_all('th')}]
    if len(tables) != 1:
        raise ValueError('Missing or ambiguous league member table')
    body = tables[0].find('tbody')
    if body is None:
        raise ValueError('Missing league member rows')
    result, seen = [], set()
    for row in body.find_all('tr', recursive=False):
        links = row.select('td.hauptlink a[href]')
        club_links = []
        for link in links:
            match = re.fullmatch(r'/[^/]+/startseite/verein/(\d+)/saison_id/(\d+)', link['href'])
            if match:
                club_links.append((match[1], match[2], link.get_text(' ',strip=True)))
        if len(club_links) != 1 or club_links[0][1] != str(season) or not club_links[0][2]:
            raise ValueError('Missing, ambiguous or stale club identity')
        club_id, _, name = club_links[0]
        if club_id in seen:
            raise ValueError('Duplicate league member ID')
        seen.add(club_id)
        for link in row.find_all('a', href=True):
            linked = re.search(r'/verein/(\d+)/saison_id/(\d+)', link['href'])
            if linked and (linked[1] != club_id or linked[2] != str(season)):
                raise ValueError('Conflicting row club links')
        relegation = [span.get('title','') for span in row.select('.icon-absteiger')]
        if len(relegation) > 1:
            raise ValueError('Ambiguous relegation marker')
        result.append(dict(club_tm_id=club_id, club=name, relegation_note=relegation[0] if relegation else ''))
    if not 2 <= len(result) <= 24:
        raise ValueError('Unsupported or incomplete league table size')
    return result
