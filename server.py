def get_mode_params(level):
    if level <= 20:
        return {
            "adx": 25,
            "rsi_min": 48,
            "rsi_max": 53,
            "stoploss": -0.03,
            "roi": {"0": 0.03, "60": 0.02, "120": 0.01, "240": 0, "480": -0.02}
        }
    elif level <= 40:
        return {
            "adx": 22,
            "rsi_min": 44,
            "rsi_max": 56,
            "stoploss": -0.04,
            "roi": {"0": 0.025, "60": 0.015, "120": 0.008, "240": 0, "480": -0.02}
        }
    elif level <= 60:
        return {
            "adx": 20,
            "rsi_min": 40,
            "rsi_max": 60,
            "stoploss": -0.05,
            "roi": {"0": 0.02, "45": 0.012, "90": 0.006, "180": 0, "360": -0.02}
        }
    elif level <= 80:
        return {
            "adx": 17,
            "rsi_min": 37,
            "rsi_max": 63,
            "stoploss": -0.06,
            "roi": {"0": 0.018, "45": 0.01, "90": 0.005, "180": 0, "360": -0.02}
        }
    else:
        return {
            "adx": 15,
            "rsi_min": 35,
            "rsi_max": 65,
            "stoploss": -0.08,
            "roi": {"0": 0.015, "30": 0.008, "60": 0.004, "120": 0, "240": -0.02}
        }
