# PUBLIC SHELL VERSION
"""Category detection for Polymarket trades."""
CRYPTO_KEYWORDS = ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'solana', 'sol', 'dogecoin', 'doge', 'xrp', 'ripple', 'cardano', 'ada', 'polygon', 'matic', 'chainlink', 'link', 'avalanche', 'avax', 'binance', 'bnb', 'litecoin', 'ltc', 'polkadot', 'dot', 'shiba', 'pepe', 'memecoin', 'defi', 'nft', 'blockchain', 'altcoin', 'stablecoin', 'usdt', 'usdc', 'tether', 'coinbase', 'binance', 'kraken', 'spot etf', 'bitcoin etf', 'halving', 'mining', 'satoshi', 'vitalik', 'crypto market']
SPORTS_KEYWORDS = ['nfl', 'nba', 'mlb', 'nhl', 'fifa', 'uefa', 'premier league', 'champions league', 'world cup', 'super bowl', 'playoffs', 'football', 'basketball', 'baseball', 'hockey', 'soccer', 'tennis', 'golf', 'boxing', 'ufc', 'mma', 'f1', 'formula 1', 'olympics', 'match', 'game', 'score', 'vs ', ' vs', 'sports', 'acn', 'afcon', 'afc', 'concacaf', 'copa america', 'euro 2024', 'euro 2028', 'lakers', 'celtics', 'warriors', 'knicks', 'bulls', 'nets', 'sixers', '76ers', 'bucks', 'heat', 'suns', 'mavericks', 'mavs', 'clippers', 'kings', 'nuggets', 'thunder', 'okc', 'spurs', 'sas', 'rockets', 'jazz', 'grizzlies', 'pelicans', 'timberwolves', 'wolves', 'blazers', 'hornets', 'magic', 'wizards', 'hawks', 'pacers', 'pistons', 'cavaliers', 'cavs', 'raptors', 'manchester', 'liverpool', 'arsenal', 'chelsea', 'real madrid', 'barcelona', 'bayern', 'juventus', 'psg', 'inter milan', 'ac milan', 'tottenham', 'newcastle', 'aston villa', 'dortmund', 'cowboys', 'patriots', 'chiefs', 'eagles', 'bills', 'ravens', '49ers', 'niners', 'steelers', 'packers', 'giants', 'dolphins', 'jets', 'bengals', 'browns', 'lions', 'bears', 'vikings', 'commanders', 'texans', 'colts', 'jaguars', 'titans', 'chargers', 'raiders', 'broncos', 'seahawks', 'cardinals', 'rams', 'saints', 'buccaneers', 'bucs', 'panthers', 'falcons', 'argentina', 'brazil', 'france', 'germany', 'england', 'spain', 'portugal', 'italy', 'netherlands', 'belgium', 'croatia', 'morocco', 'japan', 'south korea', 'usa', 'mexico', 'canada', 'australia', 'senegal', 'cameroon', 'nigeria', 'egypt', 'ghana', 'lebron', 'curry', 'durant', 'mahomes', 'brady', 'messi', 'ronaldo', 'mvp', 'championship', 'finals', 'touchdown', 'goal', 'home run', 'slam dunk', 'knockout', 'winner', 'points', 'assists', 'rebounds', ' beat ', ' defeat ', 'victory', 'loses', 'advance', 'sporting cp', 'benfica', 'porto', 'braga', 'ajax', 'feyenoord', 'psv', 'celtic', 'rangers', 'rio ave', 'vitoria', 'moreirense', 'spl', 'saudi pro league', 'al nassr', 'al hilal', 'al ahli', 'al ittihad', 'al ettifaq', 'al shabab', 'saudi']

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