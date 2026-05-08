"""
state_configs/ohio.py
─────────────────────
Schema mapping for Ohio Secretary of State Statewide Voter File (SWVF).

Structure
---------
COLUMN_MAP : dict[str, str]
    Maps raw source column names → internal canonical names used throughout
    the pipeline.  Add a new state by creating state_configs/<state>.py with
    its own COLUMN_MAP pointing to the same canonical names.

PARTY_MAP : dict[str, str]
    Maps raw party codes → display labels (REP / DEM / UNC / Other).

VOTER_STATUS_ACTIVE : str
    The exact string value in the status column that means "active voter".

VOTER_STATUS_CONFIRMATION : str
    The exact string value meaning "confirmation / inactive".

COUNTY_FIELD : str
    Raw column name that holds the county identifier used for partitioning.

SOURCE_ENCODING : str
    File encoding passed to Polars scan_csv.

SOURCE_SEPARATOR : str
    Field delimiter.
"""

# ── Column map: raw → canonical ───────────────────────────────────────────────
# Keys are exact column names as they appear in the SWVF header row.
# Values are the canonical names used everywhere else in the pipeline.
# Columns not listed here are passed through unchanged (election participation
# columns follow a date-based naming convention and are detected by regex).

COLUMN_MAP: dict[str, str] = {
    # Identity
    'SOS_VOTERID':                    'SOS_VOTERID',
    'COUNTY_NUMBER':                  'COUNTY_NUMBER',
    'COUNTY_ID':                      'COUNTY_ID',
    'LAST_NAME':                      'LAST_NAME',
    'FIRST_NAME':                     'FIRST_NAME',
    'MIDDLE_NAME':                    'MIDDLE_NAME',
    'SUFFIX':                         'SUFFIX',

    # Address
    'RESIDENTIAL_ADDRESS1':           'RESIDENTIAL_ADDRESS1',
    'RESIDENTIAL_SECONDARY_ADDR':     'RESIDENTIAL_SECONDARY_ADDR',
    'RESIDENTIAL_CITY':               'RESIDENTIAL_CITY',
    'RESIDENTIAL_STATE':              'RESIDENTIAL_STATE',
    'RESIDENTIAL_ZIP':                'RESIDENTIAL_ZIP',
    'RESIDENTIAL_ZIP_PLUS4':          'RESIDENTIAL_ZIP_PLUS4',
    'RESIDENTIAL_COUNTRY':            'RESIDENTIAL_COUNTRY',
    'RESIDENTIAL_POSTALCODE':         'RESIDENTIAL_POSTALCODE',
    'MAILING_ADDRESS1':               'MAILING_ADDRESS1',
    'MAILING_SECONDARY_ADDRESS':      'MAILING_SECONDARY_ADDRESS',
    'MAILING_CITY':                   'MAILING_CITY',
    'MAILING_STATE':                  'MAILING_STATE',
    'MAILING_ZIP':                    'MAILING_ZIP',
    'MAILING_ZIP_PLUS4':              'MAILING_ZIP_PLUS4',
    'MAILING_COUNTRY':                'MAILING_COUNTRY',
    'MAILING_POSTAL_CODE':            'MAILING_POSTAL_CODE',

    # Demographics / registration
    'DATE_OF_BIRTH':                  'DATE_OF_BIRTH',
    'REGISTRATION_DATE':              'REGISTRATION_DATE',
    'VOTER_STATUS':                   'VOTER_STATUS',
    'PARTY_AFFILIATION':              'PARTY_AFFILIATION',
    'PRECINCT_NAME':                  'PRECINCT_NAME',
    'PRECINCT_CODE':                  'PRECINCT_CODE',
    'COUNTY_BOARD_OF_ELECTIONS':      'COUNTY_BOARD_OF_ELECTIONS',

    # Districts
    'CONGRESSIONAL_DISTRICT':         'CONGRESSIONAL_DISTRICT',
    'STATE_SENATE_DISTRICT':          'STATE_SENATE_DISTRICT',
    'STATE_REPRESENTATIVE_DISTRICT':  'STATE_REPRESENTATIVE_DISTRICT',
    'STATE_BOARD_OF_EDUCATION':       'STATE_BOARD_OF_EDUCATION',
    'LOCAL_SCHOOL_DISTRICT':          'LOCAL_SCHOOL_DISTRICT',
    'CITY':                           'CITY',
    'CITY_SCHOOL_DISTRICT':           'CITY_SCHOOL_DISTRICT',
    'EXEMPTED_VILLAGE_SCHOOL_DISTRICT': 'EXEMPTED_VILLAGE_SCHOOL_DISTRICT',
    'EDUCATIONAL_SERVICE_CENTER':     'EDUCATIONAL_SERVICE_CENTER',
    'COUNTY_COURT_DISTRICT':          'COUNTY_COURT_DISTRICT',
    'TOWNSHIP':                       'TOWNSHIP',
    'WARD':                           'WARD',
    'VILLAGE':                        'VILLAGE',
    'LIBRARY':                        'LIBRARY',
    'METRO_PARKS':                    'METRO_PARKS',
    'HOSPITAL_DIST':                  'HOSPITAL_DIST',
    'FIRE':                           'FIRE',
    'SANITARY':                       'SANITARY',
    'SOIL_WATER':                     'SOIL_WATER',
    'VOCATIONAL_SCHOOL':              'VOCATIONAL_SCHOOL',
    'JUDICIAL_DISTRICT':              'JUDICIAL_DISTRICT',
    'COURT_OF_APPEALS':               'COURT_OF_APPEALS',
}

# ── Party codes → display labels ──────────────────────────────────────────────
PARTY_MAP: dict[str, str] = {
    'R': 'REP',
    'D': 'DEM',
    '':  'UNC',
}

# ── Status values ─────────────────────────────────────────────────────────────
VOTER_STATUS_ACTIVE:       str = 'ACTIVE'
VOTER_STATUS_CONFIRMATION: str = 'CONFIRMATION'

# ── File format ───────────────────────────────────────────────────────────────
COUNTY_FIELD:     str = 'COUNTY_NUMBER'
SOURCE_ENCODING:  str = 'utf8-lossy'
SOURCE_SEPARATOR: str = ','
