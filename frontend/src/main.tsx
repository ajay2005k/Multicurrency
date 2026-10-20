import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ShieldCheck,
  LayoutDashboard,
  ArrowLeftRight,
  Plus,
  Search,
  ArrowUpRight,
  Globe2,
  ChevronRight,
  X,
  Check,
  AlertTriangle,
  Ban,
  Activity,
  Settings,
  RefreshCw,
  Loader2,
  CreditCard,
  ArrowDownLeft,
  Menu,
  KeyRound,
} from "lucide-react";
import "./style.css";

type Decision = "approve" | "review" | "deny";
type Transaction = {
  id: string;
  created_at: string;
  amount: number;
  currency: string;
  customer_id: string;
  merchant: string;
  country: string;
  billing_country: string;
  usd_amount: number;
  exchange_rate: number;
  rate_source: string;
  decision: Decision;
  risk_score: number;
  reasons: { signal: string; points: number }[];
  payment_method: string;
  device_new: boolean;
};
type Dashboard = {
  total: number;
  volume_usd: number;
  counts: Record<Decision, number>;
  approval_rate: number;
  avg_risk: number;
  daily: { date: string; volume: number; count: number }[];
  currencies: { currency: string; count: number; volume: number }[];
  fx_provider: string;
};
const labels = {
  approve: "Approved",
  review: "Needs review",
  deny: "Declined",
};
const countries: Record<string, string> = {
  US: "United States",
  GB: "United Kingdom",
  IN: "India",
  DE: "Germany",
  FR: "France",
  JP: "Japan",
  CA: "Canada",
  AU: "Australia",
  CH: "Switzerland",
  SG: "Singapore",
  AE: "United Arab Emirates",
  BR: "Brazil",
  NG: "Nigeria",
  ZA: "South Africa",
  CN: "China",
  MX: "Mexico",
  NL: "Netherlands",
  ES: "Spain",
  IT: "Italy",
};
const symbols: Record<string, string> = {
  USD: "$",
  EUR: "€",
  GBP: "£",
  INR: "₹",
  JPY: "¥",
  CAD: "CA$",
  AUD: "A$",
  CHF: "CHF ",
  SGD: "S$",
  AED: "AED ",
};
const money = (n: number, c = "USD") =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: c,
    maximumFractionDigits: 2,
  }).format(n);
import { api, ApiError } from "./api";

function Badge({ decision }: { decision: Decision }) {
  const Icon =
    decision === "approve"
      ? Check
      : decision === "review"
        ? AlertTriangle
        : Ban;
  return (
    <span className={"badge " + decision}>
      <Icon size={12} />
      {labels[decision]}
    </span>
  );
}
function App() {
  const [accessRequired, setAccessRequired] = useState(false);
  const [accessError, setAccessError] = useState("");
  const [page, setPage] = useState("Overview");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [items, setItems] = useState<Transaction[]>([]);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [pay, setPay] = useState(false);
  const [selected, setSelected] = useState<Transaction | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [mobile, setMobile] = useState(false);
  const [settings, setSettings] = useState(false);
  const [apiKey, setApiKey] = useState(sessionStorage.getItem("api-key") || "");
  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([api("/api/dashboard"), api("/api/transactions?limit=500")])
      .then(([d, t]) => {
        if (active) {
          setDashboard(d);
          setItems(t.items);
          setError("");
        }
      })
      .catch((e) => {
        if (active) {
          setError(e.message);
          setAccessRequired(e instanceof ApiError && e.status === 401);
          setAccessError(
            e instanceof ApiError &&
              e.status === 401 &&
              sessionStorage.getItem("api-key")
              ? "Access key not recognized. Please check your key and try again."
              : "",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [refresh]);
  const visible = items.filter(
    (t) =>
      (filter === "all" || filter === t.decision) &&
      (!search ||
        [t.id, t.customer_id, t.merchant, t.currency]
          .join(" ")
          .toLowerCase()
          .includes(search.toLowerCase())),
  );
  const d = dashboard;
  if (accessRequired)
    return (
      <div className="access-page">
        <section className="access-story">
          <a className="brand" href="#" onClick={(e) => e.preventDefault()}>
            <span className="brand-icon">
              <ShieldCheck size={27} />
            </span>
            sentinel<span className="brand-dot">.</span>
          </a>
          <div className="access-story-content">
            <div className="eyebrow">GLOBAL PAYMENT INTELLIGENCE</div>
            <h1>
              Confidence in
              <br />
              every currency.
            </h1>
            <p>
              A single workspace to assess payment risk and understand every
              decision.
            </p>
            <div className="access-features">
              {[
                "Unified currency conversion",
                "Explainable risk decisions",
                "Searchable payment history",
              ].map((text) => (
                <span key={text}>
                  <Check size={16} />
                  {text}
                </span>
              ))}
            </div>
          </div>
          <span className="access-story-footer">
            Sentinel · Payment risk management
          </span>
        </section>
        <section className="access-form-wrap">
          <form
            className="access-form"
            onSubmit={(e) => {
              e.preventDefault();
              sessionStorage.setItem("api-key", apiKey);
              setAccessRequired(false);
              setAccessError("");
              setError("");
              setRefresh((x) => x + 1);
            }}
          >
            <div className="access-lock">
              <ShieldCheck size={26} />
            </div>
            <div className="eyebrow">YOUR PAYMENT WORKSPACE</div>
            <h2>Welcome to Sentinel</h2>
            <p>Enter your workspace access key to continue.</p>
            <label>
              Workspace access key
              <input
                type="password"
                autoFocus
                required
                autoComplete="current-password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Enter your access key"
              />
            </label>
            {accessError && (
              <div className="error" role="alert">
                {accessError}
              </div>
            )}
            <button type="submit" className="primary full">
              Connect workspace
              <ArrowUpRight size={17} />
            </button>
            <p className="access-help">
              Access is managed by your workspace administrator.
            </p>
          </form>
        </section>
      </div>
    );
  return (
    <div className="app">
      <aside className={mobile ? "sidebar open" : "sidebar"}>
        <a className="brand" href="#" onClick={(e) => e.preventDefault()}>
          <span className="brand-icon">
            <ShieldCheck size={25} />
          </span>
          sentinel<span className="brand-dot">.</span>
        </a>
        <div className="workspace">
          <span className="workspace-avatar">M</span>
          <div>
            Multicurrency<span>Payment operations</span>
          </div>
          <ChevronRight size={15} />
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav>
          {[
            { name: "Overview", icon: LayoutDashboard },
            { name: "Transactions", icon: ArrowLeftRight },
            { name: "Risk insights", icon: ShieldCheck },
          ].map((n) => (
            <button
              key={n.name}
              className={page === n.name ? "active" : ""}
              onClick={() => {
                setPage(n.name);
                setMobile(false);
                setFilter("all");
              }}
            >
              <n.icon size={18} />
              {n.name}
              {n.name === "Transactions" && <small>{d?.total || 0}</small>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sandbox">
            <span className="status-dot" />
            {error
              ? "Connection unavailable"
              : d
                ? "API connected"
                : "Connecting…"}
            <p>
              {d?.fx_provider === "live"
                ? "Live exchange rates"
                : "Reference exchange rates"}
            </p>
          </div>
          <button className="settings-link" onClick={() => setSettings(true)}>
            <Settings size={17} />
            Workspace access
          </button>
          <div className="profile">
            <div className="avatar">RO</div>
            <div>
              Risk operations<span>Workspace member</span>
            </div>
            {d && !error && <span className="online" />}
          </div>
        </div>
      </aside>
      <div className="main">
        <header>
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMobile(!mobile)}
            >
              <Menu size={20} />
            </button>
            Workspace <ChevronRight size={14} />
            <strong>{page}</strong>
          </div>
          <div className="header-right">
            <span className="environment">PAYMENT OPERATIONS</span>
            <span className="avatar small">RO</span>
          </div>
        </header>
        <main>
          <div className="heading">
            <div>
              <div className="eyebrow">PAYMENT INTELLIGENCE</div>
              <h1>
                {page === "Overview"
                  ? "Payment overview"
                  : page === "Transactions"
                    ? "Transactions"
                    : "Risk insights"}
              </h1>
              <p>
                {page === "Overview"
                  ? "Track payment activity, currency exposure, and risk decisions."
                  : page === "Transactions"
                    ? "Track, inspect, and understand every payment decision."
                    : "Transparent rules. Explainable decisions. Better visibility."}
              </p>
            </div>
            <button className="primary" onClick={() => setPay(true)}>
              <Plus size={17} />
              Validate payment
            </button>
          </div>
          <div className="notice">
            <span>
              <Globe2 size={17} />
              <strong>Cross-currency risk analysis</strong>
              <span>Assess global payments with a consistent risk policy.</span>
            </span>
            <span className="notice-tag">
              {d?.fx_provider === "live" ? "LIVE RATES" : "REFERENCE RATES"}
            </span>
          </div>
          {error && (
            <div className="error" role="alert">
              {error}
              <button onClick={() => setRefresh((x) => x + 1)}>Retry</button>
            </div>
          )}
          <section className="stats">
            <Stat
              title="Total payment volume"
              value={money(d?.volume_usd || 0)}
              icon={<ArrowUpRight size={19} />}
              note={`${d?.total || 0} ${d?.total === 1 ? "transaction" : "transactions"} · USD equivalent`}
            />
            <Stat
              title="Approval rate"
              value={`${d?.approval_rate || 0}%`}
              icon={<ShieldCheck size={19} />}
              note={`${d?.counts.approve || 0} ${d?.counts.approve === 1 ? "payment" : "payments"} approved`}
              green
            />
            <Stat
              title="Flagged payments"
              value={String(
                (d?.counts.review || 0) + (d?.counts.deny || 0),
              ).padStart(2, "0")}
              icon={<AlertTriangle size={19} />}
              note={`${d?.counts.review || 0} need review · ${d?.counts.deny || 0} declined`}
            />
            <Stat
              title="Average risk score"
              value={`${d?.avg_risk || 0}`}
              icon={<Activity size={19} />}
              note="Out of 100 · higher means riskier"
            />
          </section>
          {page === "Risk insights" ? (
            <section className="panel rules-panel">
              <div className="panel-title">
                <div>
                  <h2>How decisions are made</h2>
                  <p>Your payment risk policy, explained</p>
                </div>
                <ShieldCheck size={24} />
              </div>
              <div className="rules-grid">
                {[
                  [
                    "Payment value",
                    "$2,500+ adds 20 points; $10,000+ adds 45.",
                  ],
                  [
                    "Location mismatch",
                    "Different payment and billing countries add 25 points.",
                  ],
                  ["New device", "An unfamiliar device adds 15 points."],
                  [
                    "Payment velocity",
                    "Three or more prior payments in 10 minutes add 30 points.",
                  ],
                  [
                    "Customer history",
                    "A prior denied payment adds 20 points. A first payment adds 5.",
                  ],
                  [
                    "Decision thresholds",
                    "Approve below 35; review from 35–69; deny from 70.",
                  ],
                ].map(([title, body]) => (
                  <article key={title}>
                    <ShieldCheck size={20} />
                    <h3>{title}</h3>
                    <p>{body}</p>
                  </article>
                ))}
              </div>
              <div className="method-note">
                Scores reflect the signals in your risk policy. They indicate
                relative risk, rather than the probability of fraud.
              </div>
            </section>
          ) : (
            page === "Overview" && (
              <section className="analytics">
                <div className="panel volume-panel">
                  <div className="panel-title">
                    <div>
                      <h2>Payment activity</h2>
                      <p>Payment volume across all currencies</p>
                    </div>
                    <span className="period">Last 7 days</span>
                  </div>
                  <div className="chart-summary">
                    <strong>
                      {money(d?.daily.reduce((s, x) => s + x.volume, 0) || 0)}
                    </strong>
                    <span>
                      <span className="legend-dot" />
                      Volume in USD
                    </span>
                  </div>
                  <div className="bar-chart">
                    {(
                      d?.daily ||
                      Array.from({ length: 7 }, (_, i) => ({
                        date: new Date(Date.now() - (6 - i) * 86400000)
                          .toISOString()
                          .slice(0, 10),
                        volume: 0,
                        count: 0,
                      }))
                    ).map((day) => (
                      <div className="bar-col" key={day.date}>
                        <div className="bar-area">
                          <div
                            className="bar"
                            title={`${day.date}: ${money(day.volume)} · ${day.count} payments`}
                            style={{
                              height: day.volume
                                ? `${Math.max(4, (day.volume / Math.max(...(d?.daily.map((x) => x.volume) || [1]), 1)) * 100)}%`
                                : "2px",
                            }}
                          />
                        </div>
                        <span>
                          {new Date(day.date + "T12:00:00").toLocaleDateString(
                            "en-US",
                            { weekday: "short" },
                          )}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="panel decisions-panel">
                  <div className="panel-title">
                    <div>
                      <h2>Decision breakdown</h2>
                      <p>Every payment, accounted for</p>
                    </div>
                    <ArrowUpRight size={18} />
                  </div>
                  <div
                    className="donut"
                    style={{
                      background: d?.total
                        ? `conic-gradient(#1e7960 0 ${(d.counts.approve / d.total) * 100}%, #e7b453 ${(d.counts.approve / d.total) * 100}% ${((d.counts.approve + d.counts.review) / d.total) * 100}%, #de7975 ${((d.counts.approve + d.counts.review) / d.total) * 100}% 100%)`
                        : "#edf1ef",
                    }}
                  >
                    <div>
                      <strong>{d?.total || 0}</strong>
                      <span>payments</span>
                    </div>
                  </div>
                  <div className="decision-legend">
                    {(["approve", "review", "deny"] as Decision[]).map((k) => (
                      <div key={k}>
                        <span>
                          <i className={k} />
                          {labels[k]}
                        </span>
                        <strong>
                          {d?.counts[k] || 0}
                          <small>
                            {d?.total
                              ? Math.round((d.counts[k] / d.total) * 100)
                              : 0}
                            %
                          </small>
                        </strong>
                      </div>
                    ))}
                  </div>
                </div>
              </section>
            )
          )}
          <section className="panel transactions">
            <div className="panel-title">
              <div>
                <h2>
                  {page === "Overview" ? "Recent transactions" : "Transactions"}
                  <span className="count-pill">{items.length}</span>
                </h2>
                <p>A closer look at your payment activity</p>
              </div>
              <button
                className="text-button"
                onClick={() => {
                  setPage("Transactions");
                  setRefresh((x) => x + 1);
                }}
              >
                {page === "Overview" ? "View all transactions" : "Refresh"}
                {page === "Overview" ? (
                  <ArrowUpRight size={15} />
                ) : (
                  <RefreshCw size={15} />
                )}
              </button>
            </div>
            <div className="table-tools">
              <div className="tabs">
                {[
                  ["all", "All payments"],
                  ["approve", "Approved"],
                  ["review", "Needs review"],
                  ["deny", "Declined"],
                ].map(([v, l]) => (
                  <button
                    key={v}
                    onClick={() => setFilter(v)}
                    className={filter === v ? "selected" : ""}
                  >
                    {l}
                  </button>
                ))}
              </div>
              <label className="search">
                <Search size={16} />
                <input
                  placeholder="Search transactions..."
                  aria-label="Search transactions"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </label>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>TRANSACTION / MERCHANT</th>
                    <th>AMOUNT</th>
                    <th>CUSTOMER</th>
                    <th>RISK SCORE</th>
                    <th>STATUS</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {(page === "Overview" ? visible.slice(0, 5) : visible).map(
                    (t) => (
                      <tr
                        key={t.id}
                        onClick={() => setSelected(t)}
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") setSelected(t);
                        }}
                      >
                        <td>
                          <div className="merchant-cell">
                            <span className="merchant-icon">
                              <ArrowDownLeft size={17} />
                            </span>
                            <div>
                              <strong>{t.merchant}</strong>
                              <small>
                                {t.id} ·{" "}
                                {new Date(t.created_at).toLocaleDateString(
                                  undefined,
                                  { month: "short", day: "numeric" },
                                )}
                              </small>
                            </div>
                          </div>
                        </td>
                        <td>
                          <strong>{money(t.amount, t.currency)}</strong>
                          <small>
                            {t.currency !== "USD"
                              ? money(t.usd_amount) + " USD"
                              : "US Dollar"}
                          </small>
                        </td>
                        <td>
                          <span className="customer">{t.customer_id}</span>
                          <small>{countries[t.country] || t.country}</small>
                        </td>
                        <td>
                          <div className="risk">
                            <span className={"risk-dot " + t.decision} />
                            <strong>{t.risk_score}</strong>
                            <span className="risk-track">
                              <i
                                className={t.decision}
                                style={{ width: `${t.risk_score}%` }}
                              />
                            </span>
                          </div>
                        </td>
                        <td>
                          <Badge decision={t.decision} />
                        </td>
                        <td>
                          <ChevronRight size={16} />
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
            {!visible.length && (
              <div className="empty">
                <span>
                  <ArrowLeftRight size={26} />
                </span>
                <h3>
                  {loading
                    ? "Loading your workspace…"
                    : search || filter !== "all"
                      ? "No matching transactions"
                      : "Your first payment starts here"}
                </h3>
                <p>
                  {search || filter !== "all"
                    ? "Try another search or status filter."
                    : "Submit a payment assessment to start tracking activity and risk decisions."}
                </p>
                {!search && filter === "all" && (
                  <button className="secondary" onClick={() => setPay(true)}>
                    <Plus size={15} />
                    Validate a payment
                  </button>
                )}
              </div>
            )}
            <div className="table-footer">
              Showing{" "}
              {page === "Overview"
                ? Math.min(5, visible.length)
                : visible.length}{" "}
              of {visible.length} matching transactions
              <span>
                <ShieldCheck size={13} />
                Risk policy applied
              </span>
            </div>
          </section>
          <footer>
            <span>
              <ShieldCheck size={14} />
              Sentinel · Built for a world without borders.
            </span>
            <span>All amounts normalized to USD</span>
          </footer>
        </main>
      </div>
      {pay && (
        <PaymentModal
          onClose={() => setPay(false)}
          onSuccess={(t) => {
            setPay(false);
            setSelected(t);
            setRefresh((x) => x + 1);
          }}
        />
      )}
      {selected && <Detail t={selected} onClose={() => setSelected(null)} />}
      {settings && (
        <div className="overlay" onClick={() => setSettings(false)}>
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label="Workspace access"
            onClick={(e) => e.stopPropagation()}
          >
            <ModalHead
              title="Workspace access"
              sub="Manage access to your payment workspace"
              close={() => setSettings(false)}
            />
            <p className="settings-copy">
              Enter the workspace access key provided by your administrator.
              Your access key is kept for this browser session.
            </p>
            <label>
              Workspace access key
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                autoComplete="off"
              />
            </label>
            <button
              className="primary full"
              onClick={() => {
                apiKey
                  ? sessionStorage.setItem("api-key", apiKey)
                  : sessionStorage.removeItem("api-key");
                setSettings(false);
                setRefresh((x) => x + 1);
              }}
            >
              <KeyRound size={16} />
              Connect workspace
            </button>
          </section>
        </div>
      )}
    </div>
  );
}
function Stat({
  title,
  value,
  note,
  icon,
  green = false,
}: {
  title: string;
  value: string;
  note: string;
  icon: React.ReactNode;
  green?: boolean;
}) {
  return (
    <article className="stat">
      <div className="stat-top">
        {title}
        <span>{icon}</span>
      </div>
      <strong className={green ? "green" : ""}>{value}</strong>
      <p>{note}</p>
    </article>
  );
}
function ModalHead({
  title,
  sub,
  close,
}: {
  title: string;
  sub: string;
  close: () => void;
}) {
  return (
    <div className="modal-head">
      <div>
        <div className="eyebrow">SENTINEL PAYMENTS</div>
        <h2>{title}</h2>
        <p>{sub}</p>
      </div>
      <button className="icon-button" aria-label="Close dialog" onClick={close}>
        <X size={20} />
      </button>
    </div>
  );
}
function PaymentModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: (t: Transaction) => void;
}) {
  const [form, setForm] = useState({
    amount: "",
    currency: "USD",
    customer_id: "",
    merchant: "",
    country: "US",
    billing_country: "US",
    payment_method: "card",
    device_new: false,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [key, setKey] = useState(crypto.randomUUID());
  function update(name: string, value: string | boolean) {
    setForm((f) => ({ ...f, [name]: value }));
    setKey(crypto.randomUUID());
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onSuccess(
        await api("/api/payments/validate", {
          method: "POST",
          headers: { "Idempotency-Key": key },
          body: JSON.stringify({ ...form, amount: Number(form.amount) }),
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div
      className="overlay"
      onClick={() => {
        if (!busy) onClose();
      }}
    >
      <section
        className="modal payment-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Validate payment"
        onClick={(e) => e.stopPropagation()}
      >
        <ModalHead
          title="Validate a payment"
          sub="Convert the amount and evaluate payment risk."
          close={() => {
            if (!busy) onClose();
          }}
        />
        <form onSubmit={submit}>
          <div className="form-grid">
            <label>
              Amount
              <input
                autoFocus
                type="number"
                min="0.01"
                max="100000000"
                step="0.01"
                placeholder="0.00"
                required
                value={form.amount}
                onChange={(e) => update("amount", e.target.value)}
              />
            </label>
            <label>
              Currency
              <select
                value={form.currency}
                onChange={(e) => update("currency", e.target.value)}
              >
                {Object.keys(symbols).map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
            <label className="span-two">
              Customer reference
              <input
                placeholder="e.g. alex@example.com"
                minLength={3}
                maxLength={80}
                pattern="[a-zA-Z0-9@._+\-]+"
                required
                value={form.customer_id}
                onChange={(e) => update("customer_id", e.target.value)}
              />
            </label>
            <label className="span-two">
              Merchant
              <input
                placeholder="e.g. Acme Studio"
                minLength={2}
                maxLength={80}
                required
                value={form.merchant}
                onChange={(e) => update("merchant", e.target.value)}
              />
            </label>
            <label>
              Payment country
              <select
                value={form.country}
                onChange={(e) => update("country", e.target.value)}
              >
                {Object.entries(countries).map(([c, n]) => (
                  <option key={c} value={c}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Billing country
              <select
                value={form.billing_country}
                onChange={(e) => update("billing_country", e.target.value)}
              >
                {Object.entries(countries).map(([c, n]) => (
                  <option key={c} value={c}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <label className="span-two">
              Payment method
              <select
                value={form.payment_method}
                onChange={(e) => update("payment_method", e.target.value)}
              >
                <option value="card">Card</option>
                <option value="bank_transfer">Bank transfer</option>
                <option value="wallet">Digital wallet</option>
              </select>
            </label>
          </div>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.device_new}
              onChange={(e) => update("device_new", e.target.checked)}
            />
            <span>This is a new or unrecognized device</span>
          </label>
          <div className="form-note">
            <ShieldCheck size={17} />
            <span>
              Risk assessment only. Submitting this request does not initiate a
              charge.
            </span>
          </div>
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          <button className="primary full" disabled={busy} type="submit">
            {busy ? (
              <Loader2 size={17} className="spin" />
            ) : (
              <ShieldCheck size={17} />
            )}{" "}
            {busy ? "Analyzing payment…" : "Validate payment"}
            <ArrowUpRight size={17} />
          </button>
        </form>
      </section>
    </div>
  );
}
function Detail({ t, onClose }: { t: Transaction; onClose: () => void }) {
  return (
    <div className="overlay" onClick={onClose}>
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label="Payment result"
        onClick={(e) => e.stopPropagation()}
      >
        <ModalHead title="Payment intelligence" sub={t.id} close={onClose} />
        <div className={"result-banner " + t.decision}>
          <Badge decision={t.decision} />
          <strong>{money(t.amount, t.currency)}</strong>
          <p>
            {t.merchant} · {t.customer_id}
          </p>
        </div>
        <div className="detail-grid">
          <div>
            <span>USD equivalent</span>
            <strong>{money(t.usd_amount)}</strong>
          </div>
          <div>
            <span>Risk score</span>
            <strong>
              {t.risk_score}
              <small> / 100</small>
            </strong>
          </div>
          <div>
            <span>Exchange rate</span>
            <strong>
              1 {t.currency} = {t.exchange_rate.toFixed(6)} USD
            </strong>
          </div>
          <div>
            <span>Rate source</span>
            <strong>
              {t.rate_source === "demo"
                ? "Reference · demonstration rate"
                : "Live · ExchangeRate API"}
            </strong>
          </div>
          <div>
            <span>Payment location</span>
            <strong>{countries[t.country]}</strong>
          </div>
          <div>
            <span>Billing location</span>
            <strong>{countries[t.billing_country]}</strong>
          </div>
        </div>
        <h3 className="reason-title">What influenced this decision</h3>
        <div className="reasons">
          {t.reasons.length ? (
            t.reasons.map((r, i) => (
              <div key={i}>
                <span>
                  <Activity size={15} />
                  {r.signal}
                </span>
                <strong>+{r.points}</strong>
              </div>
            ))
          ) : (
            <p>No elevated risk signals detected.</p>
          )}
        </div>
        <p className="detail-note">
          Risk policy · {new Date(t.created_at).toLocaleString()}
          <br />A risk decision is an assessment, not a payment authorization.
        </p>
        <button className="secondary full" onClick={onClose}>
          Back to workspace
          <ChevronRight size={16} />
        </button>
      </section>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
