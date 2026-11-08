"""Bill typology from titles (rules only, no AI): who or where a bill applies to, and what it proposes.

1. Scope of application: General or public / Local application / Private or named grantee.
2. Content category: one primary category per bill (first matching rule wins, in the order below).

Basis: the reviewer's coding frame for ActCheck, and Article VI, Section 24 of the 1987 Constitution
(appropriation, revenue or tariff bills, bills authorizing an increase of the public debt, bills of
local application and private bills originate exclusively in the House of Representatives).

Titles are short, so this is an approximate, first-pass classification for browsing and charts;
the reviewer confirms the type of any bill under review.
"""
import re

APPLICATION = ["General or public", "Local application", "Private or named grantee"]

CATEGORIES = [
    ("Appropriations", r"^AN ACT APPROPRIATING|GENERAL APPROPRIATIONS|SUPPLEMENTAL APPROPRIATION|SPECIAL APPROPRIATION"
                       r"|APPROPRIATING FUNDS FOR THE OPERATION OF THE GOVERNMENT"),
    ("Legislative franchises and individual grants", r"\bFRANCHISE\b|CITIZENSHIP TO\b|NATURALI[SZ]ATION OF\b"),
    ("Commemorations, holidays and naming", r"\bHOLIDAY\b|\bDECLARING\b.{0,120}\b(DAY|WEEK|MONTH|YEAR)\b|\bRENAMING\b|\bNAMING\b"
                       r"|\bTO BE KNOWN AS\b|\bCOMMEMORAT|\bANNIVERSARY\b|FESTIVAL\b"
                       r"|\bDECLARING\b.{0,160}\b(TOURIS[TM]|ECO-?TOURISM|HERITAGE|CULTURAL)\b.{0,30}\b(DESTINATION|SITE|ZONE|SPOT|CAPITAL|AREA)"),
    ("Territorial organization and charters", r"CONVERTING THE MUNICIPALITY|INTO A (COMPONENT|HIGHLY URBANIZED|INDEPENDENT) CITY"
                       r"|CHARTER OF THE CITY|\bCITY CHARTER\b|CREATING THE (MUNICIPALITY|BARANGAY|PROVINCE)|\bLEGISLATIVE DISTRICT"
                       r"|REAPPORTION|\bBOUNDAR(Y|IES)\b|CREATING A (NEW )?(BARANGAY|MUNICIPALITY|PROVINCE)|ISLAND REGION|\bPLEBISCITE\b"),
    ("Tariffs and customs duties", r"\bTARIFF|\bCUSTOMS\b|\bIMPORT DUT|\bDUTIES\b"),
    ("Taxation and revenue", r"\bTAX(ES|ATION|ABLE)?\b|\bEXCISE\b|\bVALUE[- ]ADDED\b|INTERNAL REVENUE|\bAMNESTY\b|FISCAL INCENTIVE"
                       r"|\bREVENUE\b|\bDOCUMENTARY STAMP"),
    ("Public borrowing and debt", r"\bBORROW|\bPUBLIC DEBT\b|\bFOREIGN LOANS?\b|\bBONDS?\b|\bDEBT\b"),
    ("Public facilities and infrastructure", r"\bHOSPITAL\b|\bHIGH SCHOOL\b|\bELEMENTARY SCHOOL\b|\bSCHOOL OF\b|\bBED CAPACITY\b|\bROAD\b"
                       r"|\bBRIDGE\b|\bHIGHWAY\b|\bAIRPORT\b|\bSEAPORT\b|\bPORT\b|\bENGINEERING OFFICE\b|\bEXTENSION OFFICE\b"
                       r"|\bFIELD OFFICE\b|\bSATELLITE OFFICE\b|\bCAMPUS\b|\bCONSTRUCTION OF\b|\bSTATE (UNIVERSITY|COLLEGE)\b"
                       r"|\bSPORTS COMPLEX\b|\bEVACUATION CENT|\bDISTRICT OFFICE\b|\bBRANCH\b|\bTRIAL COURT"),
    ("Government organization and mandates", r"(CREATING|ESTABLISHING|CREATION OF|ESTABLISHMENT OF|CONSTITUTING)\b[^.;]{0,140}?\b"
                       r"(DEPARTMENT|AUTHORITY|COMMISSION|BUREAU|OFFICE|COUNCIL|AGENCY|BOARD|INSTITUTE|CORPORATION|ADMINISTRATION)\b"
                       r"|\bREORGANIZ|\bABOLISH|\bRIGHTSIZING\b|\bATTACHING THE\b|\bTRANSFERRING THE\b.{0,60}\bTO THE\b"),
    ("Public-sector compensation and personnel", r"\bSALAR(Y|IES)\b|\bCOMPENSATION OF\b|\bALLOWANCE|\bRETIREMENT\b|\bPENSION OF\b"
                       r"|\bGOVERNMENT (EMPLOYEES|WORKERS|PERSONNEL|OFFICIALS)\b|\bCIVIL SERVICE\b|\bPLANTILLA\b|\bHAZARD PAY\b"
                       r"|\bSECURITY OF TENURE\b|\bMAGNA CARTA FOR PUBLIC\b"),
    ("Emergency response and recovery", r"\bEMERGENCY\b|\bCALAMIT|\bDISASTER\b|\bPANDEMIC\b|\bBAYANIHAN\b|\bRECOVERY\b|\bSTATE OF\b"
                       r"|\bRELIEF\b|\bREHABILITATION OF\b.{0,40}(AFFECTED|TYPHOON|EARTHQUAKE)"),
    ("Public procurement and partnerships", r"\bPROCUREMENT\b|PUBLIC[- ]PRIVATE PARTNERSHIP|\bPPP\b|\bBUILD[- ]OPERATE"),
    ("Land, public assets and natural resources", r"\bLANDS?\b|\bTITL(E|ING)\b|\bPROTECTED (AREA|LANDSCAPE)|\bNATURAL PARK\b|\bFOREST"
                       r"|\bMINING\b|\bMINERAL|\bWATERSHED\b|\bRESERVATION\b|ALIENABLE AND DISPOSABLE|\bAGRARIAN\b|\bNIPAS\b"
                       r"|\bNATURAL RESOURCES\b|\bFISHERIES\b|\bMANGROVE|\bCOASTAL\b|\bREAL PROPERTY OF THE GOVERNMENT"),
    ("Offenses and penalties", r"\bPENALI[SZ]|\bPENALT(Y|IES)\b|\bCRIM(E|ES|INAL)\b|\bPUNISH|\bPROHIBIT|\bANTI[- ]|\bOFFENSES?\b"
                       r"|\bVIOLATIONS?\b|\bUNLAWFUL\b"),
    ("Rights and protections", r"\bRIGHTS?\b|\bPROTECTION OF\b|\bPROTECTING\b|\bMAGNA CARTA\b|\bWELFARE\b|\bSAFEGUARD|\bEQUALITY\b"
                       r"|\bNON-?DISCRIMINATION\b|\bDIGNITY\b"),
    ("Public programs and benefits", r"\bPROGRAMS?\b|\bSUBSID|\bSCHOLARSHIP|\bCASH\b|\bBENEFITS?\b|\bASSISTANCE\b|\bFREE\b"
                       r"|\bINSURANCE\b|\bSOCIAL PENSION\b|\bFEEDING\b|\bSERVICES?\b|\bINSTITUTIONALIZING\b|\bPRIVILEGES?\b"
                       r"|\bDISCOUNTS?\b|\bINCENTIVES?\b|\bFUND\b"),
    ("Regulation and standards", r"\bREGULAT|\bLICENS|\bREGISTRATION\b|\bSTANDARDS?\b|\bREQUIRING\b|\bMANDATING\b|\bSAFETY\b"
                       r"|\bCERTIFICATION\b|\bAMENDING\b|\bGUIDELINES\b|\bCODE\b"),
]
# last-resort rules for broad development measures, tried only when nothing above matched
FALLBACK = [("Public programs and benefits", r"\bSTRENGTHEN|\bPROMOT|\bDEVELOP|\bENHANC|\bACCESSIB|\bINDUSTRY\b|\bEDUCATION\b|\bHEALTH\b"),
            ("Regulation and standards", r"\bPROVIDING FOR\b|\bGOVERNING\b|\bPOLICY\b|\bFRAMEWORK\b")]
OTHER = "Other or unclassified"
CATEGORY_NAMES = [c for c, _ in CATEGORIES] + [OTHER]
_RX = [(c, re.compile(p, re.I)) for c, p in CATEGORIES + FALLBACK]

LOCAL_RX = re.compile(r"\b(CITY|MUNICIPALITY|PROVINCE|BARANGAY|DISTRICT|ISLAND)\s+OF\b|\bLOCATED (IN|AT)\b|\bIN THE (CITY|MUNICIPALITY|PROVINCE)\b"
                      r"|\b(LONE|FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH)\s+(LEGISLATIVE\s+)?DISTRICT\b|ISLAND REGION", re.I)
PRIVATE_RX = re.compile(r"\bFRANCHISE\b|CITIZENSHIP TO\b|NATURALI[SZ]ATION OF\b|\bGRANTING\b.{0,80}\b(INC\.?|CORPORATION|COMPANY|CO\.)", re.I)

HOUSE_ONLY = {"Appropriations", "Taxation and revenue", "Tariffs and customs duties", "Public borrowing and debt"}


def category(title):
    t = title or ""
    for c, rx in _RX:
        if rx.search(t):
            return c
    return OTHER


def application(title, cat=None):
    t = title or ""
    if PRIVATE_RX.search(t):
        return "Private or named grantee"
    if LOCAL_RX.search(t) or (cat or category(t)) == "Territorial organization and charters":
        return "Local application"
    return "General or public"


def house_origin(cat, app):
    """True if Art. VI, Sec. 24 requires this kind of bill to originate in the House."""
    return cat in HOUSE_ONLY or app in ("Local application", "Private or named grantee")
