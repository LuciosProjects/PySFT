
from dataclasses import dataclass, field
from typing import Literal
import random

MYPORTFOLIO = [ # TASE indicators
                "5138094", "1144633", "5111422", "5117379", "1159094", "1159169", "1186063", "1183441",
                # US symbols
               "GOOG", "NVDA", "IBIT", "DGRO", "JEPI", "SCHD", "IAU", "O"]

US_SYMBOLS = ["GOOG", "SCHD", "NVDA", "VOO", "DGRO", "JEPI", "IBIT", "IAU"]
EUROPEAN_SYMBOLS = ['ASML', 'SAP', 'NESN.SW', 'ROG.SW', 'NOVN.SW', 'MC.PA', 'OR.PA', 'SAN.PA', 'INGA.AS', 'SIE.DE']
TASE_INDICATORS = [ "5138094", "1134402", "1144633", "1183441", 
                    "5111422", "5117379", "1159094", "1159169", "1186063"]

FIFTY_INDICATORS = [ 
        # Major US Tech Stocks (10)
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'NFLX', 'ADBE', 'CRM',

        # US Financial Sector (5)
        'JPM', 'BAC', 'WFC', 'GS', 'MS',

        # US Healthcare & Pharma (5)
        'JNJ', 'PFE', 'UNH', 'ABBV', 'MRK',

        # US Energy & Utilities (5)
        'XOM', 'CVX', 'COP', 'EOG', 'SLB',

        # US Consumer & Retail (5)
        'WMT', 'HD', 'PG', 'KO', 'PEP',

        # Israeli Stocks - Tel Aviv Stock Exchange (10)
        '1144633', '1081124', '126.1.CHKP', '273011', '746016', '1100007', '695437', '1119478', '126.1.FSLR', '1101534',

        # European Stocks (5)
        'ASML', 'SAP', 'NESN.SW', 'ROG.SW', 'NOVN.SW',

        # Asian Stocks (5)
        'TSM', 'BABA', 'JD', 'NIO', 'BIDU'
    ]

YF400_TASE100 = [
        # US indicators
        "A", "AA", "AACB", "AACI", "AAL", "AAM", "AAME", "AAMI", "AAOI", "AAON", "AAP", "AAPL", "AARD", "AB", "ABAT", "ABBV", "ABCB", "ABCL", "ABEO", "ABG", "ABL", "ABLV", "ABM", "ABNB", "ABOS", "ABP", "ABSI", "ABT", "ABTC", "ABTS", "ABUS", "ABVC", "ACLS", "ACLX", "ACM", "ACMR", "ACN", "ACNB",
        "BA", "BAC", "BACC", "BBY", "BAX", "BATL", "BATRA", "BARK", "BE", "BEEP", "BENF", "BFC", "BGLC", "BHF", "BH", "BIP", "BIPC", "BIRD", "BIRK", "BKH", "BKNG", "BLBD", "BLK", "BRK-A", "BTCT", "BTM", "BTOG", "BULL", "BVFL", 
        "C", "CADE", "CALC", "CAMT", "CAPS", "CAPT", "CAT", "CAVA", "CBT", "CBUS", "CCIX", "CCSI", "CFFI", "CHAI", "CHE", "CHH", "CHPT", "CIFR", "CISO", "CLH", "CMCSA", "CMG",
        "D", "DGRO", "DAAQ", "DAL", "DAIO", "DAKT", "DBX", "DC", "DELL", "DK", "DKL", "DPZ", "DUOL", "DVLT", "DYN",
        "EA", "EB", "EBAY", "EG", "EHLD", "EL", "ENR", "ENVA", "EPM", "EPSN", "EQ", "EQX", "EURK", "EWBC", "EZPW",
        "F", "FAF", "FARM", "FAT", "FC", "FCF", "FCUV", "FDS", "FDX", "FE", "FFBC", "FFIN", "FGI", "FHB", "FIEE", "FIVN", "FLD", "FLL", "FLNT", "FLUT", "FLY", "FNLC", "FOA", "FORA", "FOSL", "FRBA", "FRGT", "FROG", "FUNC", "FVRR", 
        "G", "GE", "GM", "GNE", "GNRC", "GNW", "GOOG", "GRMN", "GRO", "GROW", "GSAT", "GTLB", 
        "H", "HAS", "HAYW", "HBIO", "HBNC", "HCSG", "HD", "HDSN", "HIHO", "HLF", "HOOD", "HUBB", "HUBS", "HVII", "HWC", "HWKN", 
        "IAC", "IAI", "IAT", "IAU", "IAUI", "IBAT", "IBB", "IBIT", "IBMP", "IBND", "IBOT", "ICLO", "IDLV", "IDMO", "IDNA", "IDU", "IEF", "IETC", "IETH", "IFGL", "IG", 
        "JAAA", "JADE", "JAJL", "JANB", "JANH", "JANJ", "JANM", "JAVA", "JBBB", "JBND", "JCHI", "JDVI", "JEMA", "JEPI", "JFLI", "JFLX", "JGLO", "JGRO", "JHAC", 
        "KAPR", "KARS", "KAT", "KBE", "KCAI", "KDEC", "KEAT", "KEMX", "KHPI", "KIE", "KJAN", "KJD", "KJUL", "KLIP", 
        "LABD", "LABU", "LABX", "LALT", "LAPR", "LAYS", "LBAY", "LBO", "LCAP", "LCLG", "LCOW", "LCR", "LCTD", "LDRI", "LDRT", "LDSF", "LEAD", 
        "MADE", "MAGA", "MAGC", "MAGG", "MAGS", "MAGX", "MAGY", "MAKX", "MBOX", "MBS", "MBSD", "MBSF", "MBSX", "MCDS", "MCH", "MCHI", "MCHS", "MCOW", "MCSE", "MDAA", "MDBX", "MDEV", "MDIV", 
        "NACP", "NVDA", "NAIL", "NANC", "NANR", "NAPR", "NATO", "NAUG", "NBCE", "NBCM", "NBCR", "NUKZ", "NULC", "NULG", "NULV", "NUMG", "NUMI", "NUMV", "NURE", "NUSA", "NXTI", "NXUS", "NYF", "NZAC", 
        "OACP", "OAEM", "OAIM", "OAKM", "O", "OALC", "OARK", "OBOR", "OCTJ", 
        "PAAA", "PABD", "PABU", "PALC", "PALD", "PALL", "PALU", "PAMC", "PAPI", 
        "QABA", "QAI", "QALT", "QARP", "QAT", "QB", "QBER", "QBF", 
        "RAA", "RAAA", "RAAX", "RAFE", "RAVI", "RAYC", "RAYD", 
        "SAA", "SAEF", "SAGP", "SCHD", "SAPH", "SARK", "SATO",
        "TBF", "TBFC", "TBFG", "TBG", "TBIL", 
        "UAE", "UAPR", "UBND", "UBR", "UCC", "UCO", 
        "VABS", "VALQ", "VAW", "VB", "VBIL", "VBK", 
        "WAR", "WBIF", "WBIG", "WCAP", "WCME", 
        "XAR", "XBB", "XBI", "XBIL", "XBJA", 
        "YCL" , "YCS", "YEAR", "YETH", "YFFI", 
        "ZALT", "ZAP", "ZAPR", "ZAUG", 

        # TASE indicators
        "5138094", "1144633", "5111422", "5117379", "1159094", "1159169", "1186063", "1183441", "5139605", "1159235", 
        "1147362", "1150200", "1176031", "1149335", "1144336", "1149772", "1146679", "1144237", "1185164", "1201003", 
        "5122569", "5124573", "1143866", "1145804", "1147073", "5137203", "5123153", "5122163", "1185172", "5129218", 
        "5125612", "5122940", "5130752", "5121843", "1150614", "1150226", "1149871", "1144724", "1146208", "1149889", 
        "1143833", "1146182", "1183490", "1150275", "1149301", "1144450", "5119318", "1145812", "1146737", "1200435", 
        "5139100", "5131628", "5127527", "1201664", "1165810", "1165828", "5125869", "5139282", "1201656", "5123021", 
        "5139290", "5122957", "5129275", "5124482", "5127469", "5122627", "5123161", "1159250", "5130851", "5118419", 
        "1150333", "1150572", "5113998", "5117601", "1149020", "1146471", "1144385", "1148162", "1149137", "1143817", 
        "1146604", "5138474", "5138383", "5137807", "1207208", "5136833", "1149970", "5138201", "1150242", "1206895",
        "5128079", "1146729", "5129739", "5124284", "1145713", "1150549", "1144484", "1145234", "5136064", "1144419"
    ]

@dataclass
class indicatorsDB:
    PORTFOLIO      = MYPORTFOLIO
    US             = US_SYMBOLS
    EUROPE         = EUROPEAN_SYMBOLS
    TASE           = TASE_INDICATORS
    FIFTY          = FIFTY_INDICATORS
    YF400_TASE100  = YF400_TASE100

    @staticmethod
    def getShuffeledPortfolio(fieldName: Literal["PORTFOLIO", "US", "EUROPE", "TASE", "FIFTY", "YF400_TASE100"]) -> list[str]:
        
        indicatorList = getattr(indicatorsDB, fieldName)
        shuffled = indicatorList.copy()
        random.shuffle(shuffled)
        return shuffled