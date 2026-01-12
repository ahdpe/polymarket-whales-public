"""Category detection for Polymarket trades."""

# Crypto-related keywords
CRYPTO_KEYWORDS = [
    'bitcoin', 'btc', 'ethereum', ' eth ', 'crypto', 'solana', ' sol ',
    'dogecoin', 'doge', 'xrp', 'ripple', 'cardano', 'ada', 'polygon',
    'matic', 'chainlink', 'link', 'avalanche', 'avax', 'binance', 'bnb',
    'litecoin', 'ltc', 'polkadot', 'dot', 'shiba', 'pepe', 'memecoin',
    'defi', 'nft', 'blockchain', 'altcoin', 'stablecoin', 'usdt', 'usdc',
    'tether', 'coinbase', 'binance', 'kraken exchange', 'kraken.com', 'kraken crypto', 'spot etf', 'bitcoin etf',
    'halving', 'mining', 'satoshi', 'vitalik', 'crypto market',
]

# Economics/Finance keywords (exclude from sports even if URL has /sports/)
ECONOMICS_KEYWORDS = [
    'fed', 'federal reserve', 'interest rate', 'interest rates', 'fomc',
    'basis point', 'basis points', 'bps', 'federal funds', 'monetary policy',
    'inflation', 'cpi', 'unemployment', 'gdp', 'economic', 'economy',
    'treasury', 'bond', 'yield', 'recession', 'stimulus', 'quantitative easing',
    'central bank', 'ecb', 'boj', 'boe', 'rate cut', 'rate hike', 'rate increase',
    'rate decrease', 'policy decision', 'meeting decision',
]

# Geopolitics/Military/Political keywords (exclude from sports before country name check)
GEOPOLITICS_KEYWORDS = [
    # Military/Geopolitics
    'strike', 'military strike', 'airstrike', 'air strike', 'bomb', 'bombing',
    'invasion', 'invade', 'war', 'conflict', 'attack', 'missile',
    'sanctions', 'treaty', 'diplomacy', 'diplomatic', 'embassy', 'coup',
    'nuclear', 'weapons', 'armed forces', 'military action',
    'regime', 'insurgent', 'rebel', 'ceasefire', 'military',
    
    # Politics
    'presidential election', 'presidential race', 'president', 'vice president',
    'presidential nomination', 'nomination', 'republican', 'democrat', 'democratic',
    'election', 'senate', 'senator', 'congress', 'congressman', 'congresswoman',
    'governor', 'mayor', 'political', 'politics', 'campaign', 'voter',
    'ballot', 'primary', 'caucus', 'electoral', 'impeach', 'legislative',
    'parliament', 'prime minister', 'minister', 'cabinet',
    
    # Entertainment/Awards
    'oscar', 'oscars', 'academy award', 'emmy', 'emmys', 'golden globe',
    'best actress', 'best actor', 'best director', 'best picture', 'best film',
    'grammy', 'grammys', 'tony', 'tonys', 'bafta', 'cannes', 'sundance',
    'limited series', 'tv series', 'award ceremony',
]

# Sports-related keywords
SPORTS_KEYWORDS = [
    'nfl', 'nba', 'mlb', 'nhl', 'fifa', 'uefa', 'premier league',
    'champions league', 'world cup', 'super bowl', 'playoffs',
    'football', 'basketball', 'baseball', 'hockey', 'soccer',
    'tennis', 'golf', 'boxing', 'ufc', 'mma', 'f1', 'formula 1',
    'olympics', 'match', 'game', 'score', 'vs ', ' vs',
    'sports',  # Generic
    
    # Football club abbreviations and patterns
    ' fc ', ' sv ', ' sc ', ' afc ', ' cfc ', ' bfc ', ' rfc ', ' utd',
    ' win on ', 'st mirren', 'freiburg', 'hamburger', 'macclesfield',
    
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
    'barcelona', 'bayern', 'bayer leverkusen', 'leverkusen', 'bayer 04',
    'juventus', 'psg', 'inter milan', 'ac milan',
    'tottenham', 'newcastle', 'aston villa', 'dortmund',
    
    # NFL Teams (Complete)
    'cowboys', 'patriots', 'chiefs', 'eagles', 'bills', 'ravens',
    '49ers', 'niners', 'steelers', 'packers', 'giants', 'dolphins',
    'jets', 'bengals', 'browns', 'lions', 'bears', 'vikings',
    'commanders', 'texans', 'colts', 'jaguars', 'titans', 'chargers',
    'raiders', 'broncos', 'seahawks', 'cardinals', 'rams', 'saints',
    'buccaneers', 'bucs', 'panthers', 'falcons',
    
    # NHL Teams
    'bruins', 'maple leafs', 'canadiens', 'senators', 'sabres',
    'lightning', 'panthers', 'red wings', 'blackhawks', 'predators',
    'blues', 'wild', 'jets', 'stars', 'avalanche', 'hurricanes',
    'blue jackets', 'devils', 'islanders', 'rangers', 'flyers',
    'penguins', 'capitals', 'kraken', 'canucks', 'oilers', 'flames',
    'golden knights', 'ducks', 'kings', 'sharks', 'coyotes',
    
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

    # Italian Football (Serie A/B/C)
    'serie a', 'serie b', 'serie c', 'calcio',
    'inter', 'milan', 'roma', 'napoli', 'lazio', 'fiorentina',
    'atalanta', 'torino', 'bologna', 'udinese', 'sampdoria',
    'genoa', 'verona', 'empoli', 'sassuolo', 'monza', 'lecce',
    'salernitana', 'spezia', 'cremonese', 'pisa', 'entella',

    # Spanish Football (La Liga)
    'la liga', 'almería', 'almeria', 'sevilla', 'valencia', 
    'villarreal', 'athletic bilbao', 'real sociedad', 'betis',
    'getafe', 'osasuna', 'celta', 'mallorca', 'cadiz',

    # Betting / Game Context
    'moneyline', 'spread', 'spreads', '1st half',
    'draw', 'tie', 'o/u', 'over/under', 'totals',
]


def detect_category(title: str, slug: str = "", url: str = "") -> str:
    """
    Detect the category of a trade based on its market title, URL slug, and full URL.
    Returns: 'crypto', 'sports', or 'other'
    """
    # Combine title and slug for search (slug is very useful for categories like /sports/nba/...)
    text_to_search = (title + " " + slug).lower()
    
    # First, check for explicit non-sports categories (economics, politics, etc.)
    # These should override URL-based sports detection
    for keyword in ECONOMICS_KEYWORDS:
        if keyword in text_to_search:
            # Economics/finance markets should be 'other', not 'sports'
            # Check if it's also crypto-related
            for crypto_kw in CRYPTO_KEYWORDS:
                if crypto_kw in text_to_search:
                    return 'crypto'
            return 'other'
    
    # Check for geopolitics/military context
    # These should override sports detection (e.g., "Will France strike Iran" vs "France vs Germany match")
    for keyword in GEOPOLITICS_KEYWORDS:
        if keyword in text_to_search:
            # Check if it's also crypto-related
            for crypto_kw in CRYPTO_KEYWORDS:
                if crypto_kw in text_to_search:
                    return 'crypto'
            return 'other'
    
    # Check for sports context first (before crypto to handle ambiguous cases like "Kraken vs Hurricanes")
    # If there's "vs" pattern + sports keywords, prioritize sports
    has_vs_pattern = ' vs ' in text_to_search or ' vs' in text_to_search or 'vs ' in text_to_search
    has_sports_keyword = False
    for keyword in SPORTS_KEYWORDS:
        if keyword in text_to_search:
            has_sports_keyword = True
            # If we have "vs" pattern and found sports keyword, it's definitely sports
            if has_vs_pattern:
                return 'sports'
            break
    
    # Check for crypto keywords (after sports context check)
    for keyword in CRYPTO_KEYWORDS:
        if keyword in text_to_search:
            return 'crypto'
    
    # Only use URL /sports/ if there are actual sports keywords in the title
    # This prevents misclassified markets (e.g., Fed decisions in /sports/) from being marked as sports
    if url and '/sports/' in url.lower():
        if has_sports_keyword:
            return 'sports'
        # If URL has /sports/ but no sports keywords, it's likely misclassified - check content
        # If it has economics keywords, it's already handled above
        # Otherwise, treat as 'other' to avoid false positives
    
    # If sports keywords found in title, return sports
    if has_sports_keyword:
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
