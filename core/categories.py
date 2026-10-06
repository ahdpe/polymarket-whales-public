# PUBLIC SHELL VERSION
"""Category detection for Polymarket trades."""
import re
_word_boundary_cache = {}

def _matches_keyword(text: str, keyword: str) -> bool:
    """
    Check if keyword matches in text using word boundaries.
    This prevents false positives like 'war' matching in 'Howard'.
    """
    pass
CRYPTO_KEYWORDS = ['bitcoin', 'btc', 'ethereum', ' eth ', 'crypto', 'solana', ' sol ', 'dogecoin', 'doge', 'xrp', 'ripple', 'cardano', 'ada', 'polygon', 'matic', 'chainlink', 'link', 'avalanche', 'avax', 'binance', 'bnb', 'litecoin', 'ltc', 'polkadot', 'dot', 'shiba', 'pepe', 'memecoin', 'defi', 'nft', 'blockchain', 'altcoin', 'stablecoin', 'usdt', 'usdc', 'tether', 'coinbase', 'binance', 'kraken exchange', 'kraken.com', 'kraken crypto', 'spot etf', 'bitcoin etf', 'halving', 'mining', 'satoshi', 'vitalik', 'crypto market']
ECONOMICS_KEYWORDS = ['fed', 'federal reserve', 'interest rate', 'interest rates', 'fomc', 'basis point', 'basis points', 'bps', 'federal funds', 'monetary policy', 'inflation', 'cpi', 'unemployment', 'gdp', 'economic', 'economy', 'treasury', 'bond', 'yield', 'recession', 'stimulus', 'quantitative easing', 'central bank', 'ecb', 'boj', 'boe', 'rate cut', 'rate hike', 'rate increase', 'rate decrease', 'policy decision', 'meeting decision']
GEOPOLITICS_KEYWORDS = ['strike', 'military strike', 'airstrike', 'air strike', 'bomb', 'bombing', 'invasion', 'invade', 'war', 'conflict', 'attack', 'missile', 'sanctions', 'treaty', 'diplomacy', 'diplomatic', 'embassy', 'coup', 'nuclear', 'weapons', 'armed forces', 'military action', 'regime', 'insurgent', 'rebel', 'ceasefire', 'military', 'presidential election', 'presidential race', 'president', 'vice president', 'presidential nomination', 'nomination', 'republican', 'democrat', 'democratic', 'election', 'senate', 'senator', 'congress', 'congressman', 'congresswoman', 'governor', 'mayor', 'political', 'politics', 'campaign', 'voter', 'ballot', 'primary', 'caucus', 'electoral', 'impeach', 'legislative', 'parliament', 'prime minister', 'minister', 'cabinet', 'oscar', 'oscars', 'academy award', 'emmy', 'emmys', 'golden globe', 'best actress', 'best actor', 'best director', 'best picture', 'best film', 'grammy', 'grammys', 'tony', 'tonys', 'bafta', 'cannes', 'sundance', 'limited series', 'tv series', 'award ceremony']
SPORTS_KEYWORDS = ['nfl', 'nba', 'mlb', 'nhl', 'fifa', 'uefa', 'premier league', 'champions league', 'world cup', 'super bowl', 'playoffs', 'football', 'basketball', 'baseball', 'hockey', 'soccer', 'tennis', 'golf', 'boxing', 'ufc', 'mma', 'f1', 'formula 1', 'olympics', 'match', 'game', 'score', 'vs ', ' vs', 'sports', ' fc ', ' sv ', ' sc ', ' afc ', ' cfc ', ' bfc ', ' rfc ', ' utd', ' win on ', 'st mirren', 'freiburg', 'hamburger', 'macclesfield', 'acn', 'afcon', 'afc', 'concacaf', 'copa america', 'euro 2024', 'euro 2028', 'lakers', 'celtics', 'warriors', 'knicks', 'bulls', 'nets', 'sixers', '76ers', 'bucks', 'heat', 'suns', 'mavericks', 'mavs', 'clippers', 'kings', 'nuggets', 'thunder', 'okc', 'spurs', 'sas', 'rockets', 'jazz', 'grizzlies', 'pelicans', 'timberwolves', 'wolves', 'blazers', 'hornets', 'magic', 'wizards', 'hawks', 'pacers', 'pistons', 'cavaliers', 'cavs', 'raptors', 'manchester', 'liverpool', 'arsenal', 'chelsea', 'real madrid', 'barcelona', 'bayern', 'bayer leverkusen', 'leverkusen', 'bayer 04', 'juventus', 'psg', 'inter milan', 'ac milan', 'tottenham', 'newcastle', 'aston villa', 'dortmund', 'cowboys', 'patriots', 'chiefs', 'eagles', 'bills', 'ravens', '49ers', 'niners', 'steelers', 'packers', 'giants', 'dolphins', 'jets', 'bengals', 'browns', 'lions', 'bears', 'vikings', 'commanders', 'texans', 'colts', 'jaguars', 'titans', 'chargers', 'raiders', 'broncos', 'seahawks', 'cardinals', 'rams', 'saints', 'buccaneers', 'bucs', 'panthers', 'falcons', 'bruins', 'maple leafs', 'canadiens', 'senators', 'sabres', 'lightning', 'panthers', 'red wings', 'blackhawks', 'predators', 'blues', 'wild', 'jets', 'stars', 'avalanche', 'hurricanes', 'blue jackets', 'devils', 'islanders', 'rangers', 'flyers', 'penguins', 'capitals', 'kraken', 'canucks', 'oilers', 'flames', 'golden knights', 'ducks', 'kings', 'sharks', 'coyotes', 'argentina', 'brazil', 'france', 'germany', 'england', 'spain', 'portugal', 'italy', 'netherlands', 'belgium', 'croatia', 'morocco', 'japan', 'south korea', 'usa', 'mexico', 'canada', 'australia', 'senegal', 'cameroon', 'nigeria', 'egypt', 'ghana', 'lebron', 'curry', 'durant', 'mahomes', 'brady', 'messi', 'ronaldo', 'mvp', 'championship', 'finals', 'touchdown', 'goal', 'home run', 'slam dunk', 'knockout', 'winner', 'points', 'assists', 'rebounds', ' beat ', ' defeat ', 'victory', 'loses', 'advance', 'sporting cp', 'benfica', 'porto', 'braga', 'ajax', 'feyenoord', 'psv', 'celtic', 'rangers', 'rio ave', 'vitoria', 'moreirense', 'spl', 'saudi pro league', 'al nassr', 'al hilal', 'al ahli', 'al ittihad', 'al ettifaq', 'al shabab', 'saudi', 'serie a', 'serie b', 'serie c', 'calcio', 'inter', 'milan', 'roma', 'napoli', 'lazio', 'fiorentina', 'atalanta', 'torino', 'bologna', 'udinese', 'sampdoria', 'genoa', 'verona', 'empoli', 'sassuolo', 'monza', 'lecce', 'salernitana', 'spezia', 'cremonese', 'pisa', 'entella', 'la liga', 'almería', 'almeria', 'sevilla', 'valencia', 'villarreal', 'athletic bilbao', 'real sociedad', 'betis', 'getafe', 'osasuna', 'celta', 'mallorca', 'cadiz', 'moneyline', 'spread', 'spreads', '1st half', 'draw', 'tie', 'o/u', 'over/under', 'totals']
ESPORTS_KEYWORDS = ['counter-strike', 'counter strike', 'cs:go', 'cs2', 'cs go', 'esports', 'e-sports', 'iem ', 'iem)', 'iem:', 'bo3', 'bo5', 'dota', 'dota 2', 'league of legends', 'lol ', 'valorant', 'overwatch', 'r6', 'rainbow six', 'rocket league', 'fifa esports']

def detect_category(title: str, slug: str='', url: str='') -> str:
    """
    Detect the category of a trade based on its market title, URL slug, and full URL.
    Returns: 'crypto', 'sports', or 'other'
    """
    pass

def should_show_trade(category: str, user_prefs: dict) -> bool:
    """
    Check if a trade should be shown to user based on their preferences.
    
    user_prefs format:
    {
        'all': bool,          # Show all trades
        'other': bool,        # Show non-crypto/non-sports
        'crypto': bool,       # Show crypto
        'sports': bool,       # Show sports
    }
    """
    pass
DETAILED_CATEGORY_OPTIONS = {'sports': ('sports.combo', 'sports.esports', 'sports.soccer', 'sports.basketball', 'sports.american_football', 'sports.baseball', 'sports.hockey', 'sports.tennis', 'sports.combat', 'sports.motorsport', 'sports.golf', 'sports.cricket', 'sports.other'), 'crypto': ('crypto.bitcoin', 'crypto.ethereum', 'crypto.solana', 'crypto.other_assets', 'crypto.prices', 'crypto.launches', 'crypto.regulation', 'crypto.defi_nft', 'crypto.other'), 'other': ('other.politics', 'other.geopolitics', 'other.economy', 'other.entertainment', 'other.science_tech', 'other.weather', 'other.business', 'other.other')}
_OFFICIAL_TAG_GROUPS = {'sports.esports': {'esports', 'counter-strike-2', 'cs2', 'valorant', 'league-of-legends', 'lol', 'dota-2', 'overwatch', 'rainbow-six', 'rocket-league'}, 'sports.soccer': {'soccer', 'association-football', 'fifa', 'fifa-world-cup', 'world-cup', '2026-fifa-world-cup', 'uefa', 'champions-league', 'premier-league'}, 'sports.basketball': {'basketball', 'nba', 'wnba', 'euroleague'}, 'sports.american_football': {'american-football', 'nfl', 'college-football', 'cfb'}, 'sports.baseball': {'baseball', 'mlb'}, 'sports.hockey': {'hockey', 'nhl'}, 'sports.tennis': {'tennis', 'atp', 'wta'}, 'sports.combat': {'mma', 'ufc', 'boxing', 'combat-sports'}, 'sports.motorsport': {'motorsport', 'formula1', 'formula-1', 'f1', 'nascar'}, 'sports.golf': {'golf', 'pga', 'pga-tour'}, 'sports.cricket': {'cricket', 'ipl'}, 'crypto.bitcoin': {'bitcoin', 'btc'}, 'crypto.ethereum': {'ethereum', 'eth'}, 'crypto.solana': {'solana', 'sol'}, 'crypto.other_assets': {'xrp', 'ripple', 'dogecoin', 'doge', 'cardano', 'ada', 'altcoins', 'memecoins', 'memecoin'}, 'crypto.prices': {'crypto-prices', 'hit-price', 'up-or-down', 'daily-close', 'multi-strikes', 'price-prediction'}, 'crypto.launches': {'pre-market', 'fdv', 'token-launch', 'airdrops'}, 'crypto.regulation': {'crypto-legal', 'crypto-regulation', 'regulation', 'sec', 'crypto-law'}, 'crypto.defi_nft': {'defi', 'nft', 'protocols', 'blockchain'}, 'other.politics': {'politics', 'elections', 'global-elections', 'world-elections', 'main-election', 'primaries', 'primary-elections', 'us-presidential-election', 'international-election-props'}, 'other.geopolitics': {'geopolitics', 'war', 'conflict', 'diplomacy-ceasefire', 'peace-deal', 'middle-east', 'ukraine', 'russia', 'iran', 'israel', 'china'}, 'other.economy': {'economy', 'economic-policy', 'fed', 'fed-rates', 'fomc', 'finance', 'macro-indicators', 'cpi', 'cpi-release', 'inflation', 'interest-rates', 'global-rates'}, 'other.entertainment': {'pop-culture', 'movies', 'music', 'celebrities', 'box-office', 'netflix', 'awards', 'television'}, 'other.science_tech': {'science', 'tech', 'big-tech', 'space', 'spacex', 'openai', 'artificial-intelligence', 'ai', 'earthquakes', 'natural-disaster'}, 'other.weather': {'weather', 'climate', 'climate-science', 'weather-science', 'daily-temperature', 'highest-temperature', 'lowest-temperature', 'air-quality', 'wildfire'}, 'other.business': {'business', 'ipo', 'ipos', 'companies', 'earnings'}}
_OFFICIAL_PARENT_TAGS = {'sports': {'sports'}, 'crypto': {'crypto'}}
_DETAIL_FALLBACK_KEYWORDS = {'sports.esports': ESPORTS_KEYWORDS, 'sports.soccer': ['soccer', 'association football', 'fifa', 'uefa', 'premier league', 'champions league', 'world cup'], 'sports.basketball': ['basketball', 'nba', 'wnba'], 'sports.american_football': ['nfl', 'super bowl', 'touchdown'], 'sports.baseball': ['baseball', 'mlb', 'home run'], 'sports.hockey': ['hockey', 'nhl'], 'sports.tennis': ['tennis', 'atp', 'wta'], 'sports.combat': ['mma', 'ufc', 'boxing'], 'sports.motorsport': ['formula 1', 'f1', 'nascar', 'motorsport'], 'sports.golf': ['golf', 'pga'], 'sports.cricket': ['cricket', 'ipl'], 'crypto.bitcoin': ['bitcoin', 'btc'], 'crypto.ethereum': ['ethereum', ' eth '], 'crypto.solana': ['solana', ' sol '], 'crypto.other_assets': ['xrp', 'ripple', 'dogecoin', 'doge', 'cardano', 'altcoin', 'memecoin'], 'crypto.prices': ['up or down', 'above', 'below', 'price', 'hit in'], 'crypto.launches': ['fdv', 'token launch', 'airdrop', 'pre-market'], 'crypto.regulation': ['crypto law', 'crypto regulation', 'clarity act', 'sec'], 'crypto.defi_nft': ['defi', 'nft', 'protocol', 'blockchain'], 'other.politics': ['election', 'president', 'prime minister', 'parliament', 'senate', 'congress', 'governor', 'mayor', 'nominee', 'primary', 'ballot'], 'other.geopolitics': ['war', 'invasion', 'ceasefire', 'peace deal', 'military', 'sanctions', 'airstrike', 'missile', 'treaty', 'diplomacy'], 'other.economy': ECONOMICS_KEYWORDS, 'other.entertainment': ['oscar', 'emmy', 'grammy', 'box office', 'movie', 'film', 'album', 'netflix', 'celebrity'], 'other.science_tech': ['spacex', 'starship', 'openai', 'artificial intelligence', 'earthquake', 'science', 'technology', 'ipo'], 'other.weather': ['temperature', 'weather', 'rainfall', 'snowfall', 'hurricane', 'wildfire', 'air quality', 'climate'], 'other.business': ['company', 'earnings', 'ipo', 'acquisition', 'merger']}
DETAILED_CATEGORY_EMOJIS = {'sports.combo': '🎟', 'sports.esports': '🎮', 'sports.soccer': '⚽', 'sports.basketball': '🏀', 'sports.american_football': '🏈', 'sports.baseball': '⚾', 'sports.hockey': '🏒', 'sports.tennis': '🎾', 'sports.combat': '🥊', 'sports.motorsport': '🏎️', 'sports.golf': '⛳', 'sports.cricket': '🏏', 'sports.other': '🏅', 'crypto.bitcoin': '🟠', 'crypto.ethereum': '🔷', 'crypto.solana': '🟣', 'crypto.other_assets': '🪙', 'crypto.prices': '📈', 'crypto.launches': '🚀', 'crypto.regulation': '⚖️', 'crypto.defi_nft': '🧩', 'crypto.other': '💠', 'other.politics': '🗳️', 'other.geopolitics': '🌍', 'other.economy': '📊', 'other.entertainment': '🎬', 'other.science_tech': '🔬', 'other.weather': '🌦️', 'other.business': '💼', 'other.other': '🗂️'}
_LEGACY_CATEGORY_EMOJIS = {'crypto': '💰', 'sports': '🏆', 'other': '📌'}

def get_category_emoji(legacy_category: str, detailed_categories=None) -> str:
    """Choose one deterministic card emoji from the recognized subcategories."""
    pass

def _normalize_official_tags(official_tags) -> set[str]:
    """Return normalized Gamma tag slugs from strings or tag dictionaries."""
    pass

def _matches_any_keyword(text: str, keywords) -> bool:
    pass

def _official_alias_matches(source: str, alias: str) -> bool:
    """Match exact tags and typed series prefixes such as soccer-fifwc."""
    pass

def _official_detailed_categories(official_tags) -> set[str]:
    pass

def detect_category_from_official_tags(official_tags) -> str | None:
    """Return a parent category only when Gamma metadata is unambiguous."""
    pass

def detect_detailed_categories(title: str, slug: str='', official_tags=None, legacy_category: str | None=None) -> frozenset[str]:
    """Return optional multi-label categories without changing legacy routing."""
    pass
_COMBO_LEG_SEPARATOR_RE = re.compile('\\s+AND\\s+', re.IGNORECASE)

def detect_combo_sports_categories(combo_title: str, leg_official_tags=None) -> frozenset[str]:
    """Classify every leg of a sports Combo and mark its format separately."""
    pass

def get_allowed_detailed_categories(parent: str, refinements: dict) -> set[str]:
    """Resolve effective allowed children; missing settings mean all."""
    pass

def should_show_detailed_trade(legacy_category: str, detailed_categories, refinements: dict) -> bool:
    """Apply an optional child filter after the unchanged legacy category gate."""
    pass