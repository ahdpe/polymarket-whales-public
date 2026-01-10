"""Category detection for Polymarket trades."""

# Crypto-related keywords
CRYPTO_KEYWORDS = [
    'bitcoin', 'btc', 'ethereum', ' eth ', 'crypto', 'solana', ' sol ',
    'dogecoin', 'doge', 'xrp', 'ripple', 'cardano', 'ada', 'polygon',
    'matic', 'chainlink', 'link', 'avalanche', 'avax', 'binance', 'bnb',
    'litecoin', 'ltc', 'polkadot', 'dot', 'shiba', 'pepe', 'memecoin',
    'defi', 'nft', 'blockchain', 'altcoin', 'stablecoin', 'usdt', 'usdc',
    'tether', 'coinbase', 'binance', 'kraken', 'spot etf', 'bitcoin etf',
    'halving', 'mining', 'satoshi', 'vitalik', 'crypto market',
]

# Sports-related keywords
SPORTS_KEYWORDS = [
    'nfl', 'nba', 'mlb', 'nhl', 'fifa', 'uefa', 'premier league',
    'champions league', 'world cup', 'super bowl', 'playoffs',
    'football', 'basketball', 'baseball', 'hockey', 'soccer',
    'tennis', 'golf', 'boxing', 'ufc', 'mma', 'f1', 'formula 1',
    'olympics', 'match', 'game', 'score', 'vs ', ' vs',
    'sports',  # Generic
    # Regional football competitions
    'acn', 'afcon', 'afc', 'concacaf', 'copa america', 'euro 2024', 'euro 2028',
    
    # NBA Teams
    'lakers', 'celtics', 'warriors', 'knicks', 'bulls', 'nets',
    'sixers', '76ers', 'bucks', 'heat', 'suns', 'mavericks', 'mavs',
    'clippers', 'kings', 'nuggets', 'thunder', 'okc', 'spurs', 'sas',
    'rockets', 'jazz', 'grizzlies', 'pelicans', 'timberwolves', 'wolves',
    'blazers', 'hornets', 'magic', 'wizards', 'hawks', 'pacers',
    'pistons', 'cavaliers', 'cavs', 'raptors',
    
    # Premier League / Soccer Clubs
    'manchester', 'liverpool', 'arsenal', 'chelsea', 'real madrid',
    'barcelona', 'bayern', 'juventus', 'psg', 'inter milan', 'ac milan',
    'tottenham', 'newcastle', 'aston villa', 'dortmund',
    
    # NFL Teams (Complete)
    'cowboys', 'patriots', 'chiefs', 'eagles', 'bills', 'ravens',
    '49ers', 'niners', 'steelers', 'packers', 'giants', 'dolphins',
    'jets', 'bengals', 'browns', 'lions', 'bears', 'vikings',
    'commanders', 'texans', 'colts', 'jaguars', 'titans', 'chargers',
    'raiders', 'broncos', 'seahawks', 'cardinals', 'rams', 'saints',
    'buccaneers', 'bucs', 'panthers', 'falcons',
    
    # National Soccer Teams (World Cup, etc.)
    'argentina', 'brazil', 'france', 'germany', 'england', 'spain',
    'portugal', 'italy', 'netherlands', 'belgium', 'croatia', 'morocco',
    'japan', 'south korea', 'usa', 'mexico', 'canada', 'australia',
    'senegal', 'cameroon', 'nigeria', 'egypt', 'ghana',
    
    # Players / Generic terms
    'lebron', 'curry', 'durant', 'mahomes', 'brady', 'messi', 'ronaldo',
    'mvp', 'championship', 'finals', 'touchdown', 'goal', 'home run', 
    'slam dunk', 'knockout', 'winner', 'points', 'assists', 'rebounds',
    ' beat ', ' defeat ', 'victory', 'loses', 'advance',
    
    # Portuguese League / Other Clubs
    'sporting cp', 'benfica', 'porto', 'braga',
    'ajax', 'feyenoord', 'psv', 'celtic', 'rangers',
    'rio ave', 'vitoria', 'moreirense',

    # Saudi Pro League
    'spl', 'saudi pro league', 'al nassr', 'al hilal', 
    'al ahli', 'al ittihad', 'al ettifaq', 'al shabab', 'saudi',

    # Betting / Game Context
    'moneyline', 'spread', 'spreads', '1st half',
]


def detect_category(title: str, slug: str = "", url: str = "") -> str:
    """
    Detect the category of a trade based on its market title, URL slug, and full URL.
    Returns: 'crypto', 'sports', or 'other'
    """
    # Check URL path for sports (e.g. /sports/nba/... or /sports/por/...)
    if url and '/sports/' in url.lower():
        return 'sports'
    
    # Combine title and slug for search (slug is very useful for categories like /sports/nba/...)
    text_to_search = (title + " " + slug).lower()
    
    # Check for crypto keywords
    for keyword in CRYPTO_KEYWORDS:
        if keyword in text_to_search:
            return 'crypto'
    
    # Check for sports keywords
    for keyword in SPORTS_KEYWORDS:
        if keyword in text_to_search:
            return 'sports'
    
    return 'other'


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
    if user_prefs.get('all', True):
        return True
    
    return user_prefs.get(category, False)
