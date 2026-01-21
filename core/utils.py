"""Common utility functions for PolyWhales bot."""


def shorten_trader_name(name):
    """
    Shorten trader name:
    1. Remove timestamp suffix (starting with '-') if present.
    2. Truncate long addresses: 0xB0B1Ecb5eD8a22d38Ee89f20b196246005d37507 -> 0xB0B1E...37507
    """
    if not name:
        return "Unknown"
    
    # Check if it looks like a wallet address (starts with 0x)
    clean_name = name
    if name.startswith("0x"):
        # Split by '-' to remove potential timestamp suffix
        parts = name.split('-')
        clean_name = parts[0]
        
        # If it's a long wallet address, truncate it
        if len(clean_name) > 15:
            return f"{clean_name[:7]}...{clean_name[-5:]}"
            
    return clean_name
