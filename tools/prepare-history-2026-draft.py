"""Generate a sourced offline history proposal; never writes game/database/save files."""
import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(r'C:\FM27CommunityOverhaul')
OUT = ROOT / 'data/generated/history-20260912-01'
CLUBS = ROOT / 'data/intermediate/transfer-increment-20260909-07/clubs.csv'

# country, champion, cup winner, cup runner-up, league source, cup source
TITLES = [
    (21,1376264,1376264,1376272,'https://www.dfb.de/news/neuendorf-gratuliert-dem-fc-bayern-zur-meisterschaft-beeindruckende-konstanz-und-dominanz','https://www.dfb.de/maenner/wettbewerbe/dfb-pokal/statistik/bisherige-sieger'),
    (14,917505,917518,917513,'https://www.premierleague.com/en/news/4662306','https://www.thefa.com/news/2026/may/16/emirates-fa-cup-final-chelsea-v-manchester-city-report-20261605'),
    (27,1769481,1769481,1769487,'https://www.legaseriea.it/serie-a/news/numeri-e-statistiche-della-serie-a-enilive-2025-2026','https://images.legaseriea.it/image/private/fl_attachment/prd/tlo5rdh2hfiwwtd8lgae.pdf'),
    (45,2949124,2949135,2949122,'https://www.fcbarcelona.com/en/laliga-champions-2025-2026','https://rfef.es/es/noticias/los-penaltis-coronan-la-real-sociedad-en-una-final-trepidante-2-2'),
    (18,1179663,1179664,1179666,'https://ligue1.com/fr/articles/l1_article_5187-ou-et-quand-regarder-le-trophee-des-champions-entre-le-psg-et-lens','https://ligue1.com/en/articles/l1_article_5158-'),
    (38,2490380,2494477,2490382,'https://www.ligaportugal.pt/news/27715/fc-porto-vence-e-sagra-se-campeao-nacional','https://www.sporting.pt/pt/noticias/futebol/equipa-principal/2026-05-24/derrota-na-final-da-taca-de-portugal'),
    (34,2228236,2228226,2228235,'https://www.psv.nl/media/artikel/landskampioen-psv-voor-27e-keer-kampioen-van-nederland','https://www.knvb.nl/node/71734'),
    (7,458756,458780,458766,'https://kampioen2526.clubbrugge.be/','https://www.rsca.be/nl/fixture/view/4014'),
    (48,3145825,3145826,3145839,'https://www.anadoluajansi.gov.tr/tr/spor/super-lig-2025-2026-sezonu-sampiyonu-galatasaray-oldu/3932613','https://shgm.gsb.gov.tr/HaberDetaylari/1/299950/2026-ziraat-turkiye-kupasi-sampiyonu-trabzonspor.aspx'),
    (12,786441,790540,786437,'https://www.chanceliga.cz/historie','https://www.molcup.cz/clanek/706-karvina-otocila-ve-finale-skore-a-po-vyhre-3-1-slavi-historicky-triumf'),
]

MOVES = [
    (14,'ENG',['Coventry City','Ipswich Town','Hull City'],['West Ham','Burnley','^Wolverhampton Wanderers$']),
    (27,'ITA',['Venezia','Frosinone','Monza'],['Cremonese','Hellas Verona','Pisa']),
    (45,'ESP',['Racing.*Santander','Deportivo de La Coruna','Malaga'],['Mallorca','Girona','Real Oviedo']),
    (18,'FRA',['Troyes','Le Mans'],['Nantes','Metz']),
    (38,'POR',['Maritimo','^Ac. Viseu$'],['Tondela','AVS']),
    (34,'NED',['ADO Den Haag','Cambuur','Willem II'],['NAC Breda','Heracles','^FC Volendam$']),
    (7,'BEL',['Beveren','Kortrijk','Lommel'],['Dender']),
    (48,'TUR',['Erzurumspor','Amed','Corum'],['Antalyaspor','Kayserispor','Fatih Karagumruk']),
    (12,'CZE',['Zbrojovka Brno','Artis Brno'],['Dukla Praha','Karvina']),
    (21,'GER',['Osnabruck','Energie Cottbus','SV Meppen','Fortuna Koln','Sonnenhof','Wurzburger Kickers'],['Fortuna Dusseldorf','Preu.*Munster','Erzgebirge Aue','SSV Ulm','^1. FC Schweinfurt 1905$']),
]

def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text) if not unicodedata.combining(c)).casefold()

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with CLUBS.open(encoding='utf-8-sig',newline='') as f:
        clubs={int(r['club_id']):r for r in csv.DictReader(f)}
    scope=json.loads((ROOT/'config/scope.json').read_text(encoding='utf-8-sig'))
    assert {x[0] for x in TITLES} == {x['country_id'] for x in scope['competitions']}
    rows=[]
    def add(cid,club_id,kind,field,value,source,hold=None):
        club=clubs[club_id]
        assert int(club['country_id'])==cid
        rows.append(dict(country_id=cid,club_id=club_id,reference_id=int(club['reference_id']),
                         club=club['club'],season='2025/26',kind=kind,target_field=field,
                         proposed_value=value,source=source,source_observed_date='2026-09-12',
                         status='DRAFT_SOURCE_SUPPORTED_NOT_APPLIED' if not hold else 'HOLD',
                         hold=hold,current_value=None))
    for cid,champ,winner,runner,league_source,cup_source in TITLES:
        add(cid,champ,'league_champion','mHistory.mLeagueWinYears',2026,league_source)
        add(cid,winner,'cup_winner','mHistory.mCupWinYears',2026,cup_source)
        add(cid,winner,'previous_cup_winner','mFirstTeamLastSeasonInfo.mCup','Winner',cup_source)
        add(cid,runner,'previous_cup_runner_up','mFirstTeamLastSeasonInfo.mCup','RunnerUp',cup_source)
    promotion_source='https://www.bundesliga.com/en/bundesliga/news/how-will-schalke-elversberg-paderborn-fare-promotion-38278'
    for club in [1376266,1376432,1376421]:
        add(21,club,'promoted','mFirstTeamLastSeasonInfo.mLeague','Promoted',promotion_source)
    for club,source in [(1376274,'https://www.bundesliga.com/de/bundesliga/news/sc-paderborn-vfl-wolfsburg-bundesliga-relegation-ruckspiel-aufstieg-bundesliga-37560'),(1376302,'https://www.bundesliga.com/en/bundesliga/news/heidenheim-relegated-schmidt-second-division-dorsch-ramaj-36661'),(1376425,'https://www.bundesliga.com/en/bundesliga/news/st-pauli-relegated-second-division-blessin-wolfsburg-37362')]:
        add(21,club,'relegated','mFirstTeamLastSeasonInfo.mLeague','Relegated',source)
    administrative_source='https://www.dfb.de/news/teilnehmerfeld-der-3-liga-steht-fest-havelse-rueckt-fuer-1860-nach'
    for pattern,kind,value in [('^TSV 1860 M','administrative_relegation','Relegated'),('^TSV Havelse 1912$','relegation_reprieve','None')]:
        matches=[c for c in clubs.values() if int(c['country_id'])==21 and re.search(pattern,c['club'])]
        assert len(matches)==1,(pattern,matches)
        add(21,int(matches[0]['club_id']),kind,'mFirstTeamLastSeasonInfo.mLeague',value,administrative_source)
        rows[-1]['event_date']='2026-06-11'
        rows[-1]['semantics']='Final division movement/retention marker; not a rewrite of sporting table position.'
    source_manifest=json.loads((OUT/'sources/MANIFEST.json').read_text(encoding='utf-8'))
    sources={r['country']:r for r in source_manifest if r['status']=='CAPTURED'}
    unresolved=[]
    for cid,key,promoted,relegated in MOVES:
        for kind,patterns in [('promoted',promoted),('relegated',relegated)]:
            for pattern in patterns:
                matches=[c for c in clubs.values() if int(c['country_id'])==cid and re.search(normalized(pattern),normalized(c['club']))]
                if len(matches)!=1 or key not in sources:
                    unresolved.append({'country_id':cid,'kind':kind,'pattern':pattern,'matches':matches,'reason':'Require unique club identity and captured source'})
                    continue
                c=matches[0]
                hold='LFA 03.07.2026: post-season administrative replacement, not a sporting 2025/26 promotion/relegation. Keep out of prior-season sporting flags pending explicit membership/start-date policy.' if cid==12 and ('artis' in pattern.lower() or 'karvina' in pattern.lower()) else None
                add(cid,int(c['club_id']),kind,'mFirstTeamLastSeasonInfo.mLeague',kind.title(),sources[key]['url'],hold)
                rows[-1]['source_snapshot_sha256']=sources[key]['sha256']
                rows[-1]['source_type']='RSSSF season archive; reconcile against frozen membership and primary outcome evidence before application'
                if hold:
                    rows[-1]['source']='https://www.lfafotbal.cz/clanek/958-artis-brno-doplni-ucastniky-chance-ligy-pro-sezonu-2026-27'
                    rows[-1]['secondary_source_snapshot_sha256']=rows[-1].pop('source_snapshot_sha256')
                    rows[-1]['source_type']='LFA primary decision; RSSSF retained as secondary snapshot'
                    rows[-1]['event_date']='2026-07-03'
    artifact=dict(status='OFFLINE_DRAFT_NOT_INSTALLED',season='2025/26',
                  scope=scope['competitions'],rows=rows,unresolved_movement_identities=unresolved,
                  source_binding={'clubs_path':str(CLUBS),'clubs_sha256':sha(CLUBS),'scope_sha256':sha(ROOT/'config/scope.json')},
                  limits=['No runtime, save or database mutation. Does not alter current Native08 test career.',
                          'Native current values, stale prior-season flags and append-without-duplicates checks still required before application.',
                          'Winner-year 2026 proposal must be reconciled with separate competition-history file schema before application.',
                          'Full league match results, continental history and supercups remain pending.',
                          'RSSSF snapshots captured; primary capture coverage is partial and tracked separately.'],
                  counts={'countries':len(TITLES),'proposed_field_updates':len(rows),'held':sum(r['status']=='HOLD' for r in rows),'unresolved_movement_identities':len(unresolved)})
    (OUT/'HISTORY_DRAFT.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(artifact['counts']))

if __name__=='__main__':
    main()
