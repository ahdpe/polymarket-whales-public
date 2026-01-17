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