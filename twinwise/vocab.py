"""Built-in word lists.

Twinwise treats text as sensitive unless it is known to be safe. These lists are
the starting point of that "known safe" set. Users extend them through the
safe-word list in their library.

* STOP_WORDS  - structural words that are always safe, even inside name columns.
* ACRONYMS    - common business/industry abbreviations that are always safe.
* COMMON      - ordinary business vocabulary, safe in headings, labels and notes,
                but NOT inside columns that hold names (a product called "Lantern"
                or a city called "Lakeside" must still be masked there).
* ORG_SUFFIXES - words that extend a company name ("Northwind Communications").
"""

STOP_WORDS = set("""
a an the and or of for to in on at by with from per vs via into over under as is are was were be
not no yes n/a na nil none all any each every other others misc miscellaneous total totals subtotal
grand sub net gross amount
""".split())

ACRONYMS = set("""
ppv vod svod avod tvod fast ott ctv linear est dtc b2b b2c
usd inr eur gbp cad aud jpy
ytd mtd qtd wtd yoy mom qoq wow fy cy h1 h2 q1 q2 q3 q4
id ids sku upc isbn ean uben gst vat tax tds pan
kpi roi cac ltv arpu arppu mau dau wau cpm cpc ctr cpa
hd sd uhd 4k tv vod/ppv ppv/vod svod/avod mso dma vmvpd mvpd fast avod/svod
pdf csv xlsx xls zip
llc inc ltd pvt plc corp co svp vp evp cfo ceo coo cto cmo avp
""".split())

MONTHS = set("""
jan feb mar apr may jun jul aug sep sept oct nov dec
january february march april june july august september october november december
mon tue wed thu fri sat sun monday tuesday wednesday thursday friday saturday sunday
""".split())

COMMON = set("""
account accounts accrual accruals activity actual actuals add added adjustment adjustments ad ads advertising
after agreement all allocation allocated amount amounts analysis annual api approved april area as at average avg
balance bank base based basis before begin beginning bill billed billing bonus breakdown budget business buys buy
by calculated calendar campaign cancel cancellations cancelled carriage cash category channel channels charge charges
churn city claim client clients close closing code column comment comments commission company completed consumption
content contract contracts cost costs count country credit credits currency current customer customers daily data
date dates day days deal debit deduction deductions delivered delivery description detail details device devices
digital discount discounts distribution distributor document due duration earned earnings effective end ending
engagement entity episode episodes error estimate estimated event events expense expenses fee fees file final
financial first fixed flat format free from full gross group guarantee guaranteed hour hours impression impressions
income information invoice invoiced invoices item items last late license licensee licensor line lines list
location manual market marketing master media method minimum minutes month monthly months movie movies name names
net network new notes number numbers of on order orders other overall owed package page paid partner partners
payable payment payments payout payouts percent percentage period periods plan plans platform platforms play plays
premium previous price prices pricing processed product products program programs provider providers purchase
purchases quantity quarter quarterly rate rates received receivable reconciliation record records reference refund
refunds region regional remittance remitted rental rentals report reporting reports retail revenue revenues
royalty royalties run sale sales season seasons second series service services share sheet show shows signups
source split start statement statements status stream streams streamed streaming sub subs subscriber subscribers
subscription subscriptions summary system systems tax taxes term terms territory test the title titles to top
total totals trailer transaction transactions trial trials type types unit units unique user users value values
vendor vendors video videos view viewers views week weekly weeks year yearly years ytd watch watched hours time
minutes avg average median sum min max share percent rank status active inactive gained lost opening closing
viewing beginning ending programming others other actual minimum maximum minium greater lesser value rate split
received withholding w/h holding adjusted adjustments prior current carry forward brought forward balance due
remit remitted remittance statement period thru through ending beginning starting end weekly daily total totals
dom domestic international intl usa us uk india global national local state county city country territory
signups subs churned retained reactivated paying non-paying trialists conversion conversions upgrade downgrade
gross net base bonus incentive marketing promotion promotions promo deduction rebate chargeback chargebacks
hours views starts completes completion completions sessions session minutes streams impressions clicks fill
bad debt debts cost costs sub per each devices device new old returning existing lifetime cumulative
adjustment adjustments month year amount amounts description notes note comments remarks reason source
provider providers program programs package packages tier tiers plan plans offer offers sku product
gross net payable receivable owed paid unpaid outstanding pending approved rejected disputed
accounting accountant officer chief head services service finance financial director president vice senior junior
manager controller analyst executive associate assistant lead principal partner team department dept operations
information knowledge contained best my here true correct certify certified signed signature authorized prepared
reviewed by date name title dear regards sincerely please note
""".split())

ORG_SUFFIXES = set("""
communications communication inc inc. llc l.l.c. ltd ltd. limited corp corp. corporation co co. company group
holdings media entertainment networks network studios studio pictures films productions channel channels tv
television broadcasting cable bank pvt plc gmbh sa ag bv technologies technology labs digital interactive
""".split())

# Header keywords -> category used for replacement labels.
CATEGORY_KEYWORDS = [
    ("Partner", ("partner", "customer", "client", "licensee", "licensor", "distributor", "operator", "mso", "platform", "retailer", "payer")),
    ("Vendor", ("vendor", "supplier", "payee")),
    ("Company", ("company", "account name", "organisation", "organization", "brand", "advertiser", "agency")),
    ("Channel", ("channel", "network", "station", "feed")),
    ("Title", ("title", "movie", "film", "show", "series", "episode", "program", "programme", "content", "asset")),
    ("Region", ("region", "market", "city", "state", "country", "territory", "location", "dma", "system", "headend", "zone", "area", "branch")),
    ("Email", ("email", "e-mail")),
    ("Person", ("person", "contact", "employee", "owner", "manager", "rep", "user name", "username", "first name", "last name", "full name")),
    ("Address", ("address", "street")),
]

ID_KEYWORDS = ("id", "number", "no", "no.", "#", "code", "uben", "sku", "upc", "isbn", "account", "acct", "invoice",
               "reference", "ref", "phone", "mobile", "zip", "postal", "pin", "gstin", "pan", "provider code", "order")
PERCENT_KEYWORDS = ("%", "percent", "pct", "split", "share", "rate %", "margin", "ratio")
PRICE_KEYWORDS = ("price", "rate", "fee", "cost per", "srp", "msrp", "arpu")
COUNT_KEYWORDS = ("buys", "count", "subs", "subscribers", "units", "qty", "quantity", "views", "plays", "streams",
                  "orders", "transactions", "users", "signups", "trials", "cancellations", "purchases", "rentals")
DATE_KEYWORDS = ("date", "period", "month", "year", "week", "day", "quarter", "time")


# every keyword used to recognise columns is also an ordinary word
for _cat, _kws in CATEGORY_KEYWORDS:
    COMMON.update(w for k in _kws for w in k.split())
for _group in (ID_KEYWORDS, PERCENT_KEYWORDS, PRICE_KEYWORDS, COUNT_KEYWORDS, DATE_KEYWORDS):
    COMMON.update(w for k in _group for w in k.split() if w.isalpha())
COMMON.update("""rev share watch hours contact phone mobile email address usd inr eur gbp currency""".split())
