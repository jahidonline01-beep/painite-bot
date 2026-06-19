import re

COUNTRY_CODES = {
    "1": ("United States", "🇺🇸"), "7": ("Russia", "🇷🇺"), "20": ("Egypt", "🇪🇬"),
    "27": ("South Africa", "🇿🇦"), "30": ("Greece", "🇬🇷"), "31": ("Netherlands", "🇳🇱"),
    "32": ("Belgium", "🇧🇪"), "33": ("France", "🇫🇷"), "34": ("Spain", "🇪🇸"),
    "36": ("Hungary", "🇭🇺"), "39": ("Italy", "🇮🇹"), "40": ("Romania", "🇷🇴"),
    "41": ("Switzerland", "🇨🇭"), "43": ("Austria", "🇦🇹"), "44": ("United Kingdom", "🇬🇧"),
    "45": ("Denmark", "🇩🇰"), "46": ("Sweden", "🇸🇪"), "47": ("Norway", "🇳🇴"),
    "48": ("Poland", "🇵🇱"), "49": ("Germany", "🇩🇪"), "51": ("Peru", "🇵🇪"),
    "52": ("Mexico", "🇲🇽"), "54": ("Argentina", "🇦🇷"), "55": ("Brazil", "🇧🇷"),
    "56": ("Chile", "🇨🇱"), "57": ("Colombia", "🇨🇴"), "60": ("Malaysia", "🇲🇾"),
    "61": ("Australia", "🇦🇺"), "62": ("Indonesia", "🇮🇩"), "63": ("Philippines", "🇵🇭"),
    "65": ("Singapore", "🇸🇬"), "66": ("Thailand", "🇹🇭"), "81": ("Japan", "🇯🇵"),
    "82": ("South Korea", "🇰🇷"), "84": ("Vietnam", "🇻🇳"), "86": ("China", "🇨🇳"),
    "90": ("Turkey", "🇹🇷"), "91": ("India", "🇮🇳"), "92": ("Pakistan", "🇵🇰"),
    "93": ("Afghanistan", "🇦🇫"), "94": ("Sri Lanka", "🇱🇰"), "95": ("Myanmar", "🇲🇲"),
    "98": ("Iran", "🇮🇷"), "212": ("Morocco", "🇲🇦"), "213": ("Algeria", "🇩🇿"),
    "216": ("Tunisia", "🇹🇳"), "218": ("Libya", "🇱🇾"), "220": ("Gambia", "🇬🇲"),
    "221": ("Senegal", "🇸🇳"), "234": ("Nigeria", "🇳🇬"), "233": ("Ghana", "🇬🇭"),
    "254": ("Kenya", "🇰🇪"), "255": ("Tanzania", "🇹🇿"), "256": ("Uganda", "🇺🇬"),
    "260": ("Zambia", "🇿🇲"), "263": ("Zimbabwe", "🇿🇼"), "351": ("Portugal", "🇵🇹"),
    "353": ("Ireland", "🇮🇪"), "358": ("Finland", "🇫🇮"), "380": ("Ukraine", "🇺🇦"),
    "420": ("Czech Republic", "🇨🇿"), "507": ("Panama", "🇵🇦"), "880": ("Bangladesh", "🇧🇩"),
    "886": ("Taiwan", "🇹🇼"), "960": ("Maldives", "🇲🇻"), "961": ("Lebanon", "🇱🇧"),
    "962": ("Jordan", "🇯🇴"), "964": ("Iraq", "🇮🇶"), "965": ("Kuwait", "🇰🇼"),
    "966": ("Saudi Arabia", "🇸🇦"), "967": ("Yemen", "🇾🇪"), "971": ("UAE", "🇦🇪"),
    "972": ("Israel", "🇮🇱"), "973": ("Bahrain", "🇧🇭"), "974": ("Qatar", "🇶🇦"),
    "975": ("Bhutan", "🇧🇹"), "977": ("Nepal", "🇳🇵"),
}

def detect_country_from_phone(phone: str):
    if not phone:
        return "Unknown", "🌍"
    digits = re.sub(r'\D', '', str(phone)).lstrip('0')
    for length in [3, 2, 1]:
        if len(digits) >= length:
            prefix = digits[:length]
            if prefix in COUNTRY_CODES:
                return COUNTRY_CODES[prefix]
    return "Unknown", "🌍"

def normalize_number(num: str) -> str:
    if not num:
        return ''
    return re.sub(r'\D', '', str(num)).lstrip('0')

def extract_otp(text: str) -> str:
    if not text:
        return "N/A"
    clean = text.replace("-", "")
    match = re.findall(r"\b\d{4,8}\b", clean)
    return match[0] if match else "N/A"

def html_escape(text: str) -> str:
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def mask_phone(phone: str) -> str:
    digits = re.sub(r'\D', '', phone)
    if len(digits) < 8:
        return phone
    return digits[:3] + "****" + digits[-4:]
