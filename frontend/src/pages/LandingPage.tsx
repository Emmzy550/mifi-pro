import React from 'react';
import { Link } from 'react-router-dom';
import {
    ArrowRight,
    ChevronRight,
    ShieldCheck,
    Scale,
    ScrollText,
    UsersRound,
    type LucideIcon
} from 'lucide-react';

type FlowStep = {
    title: string;
    detail: string;
};

type ArchitectureLayer = {
    title: string;
    detail: string;
    icon: LucideIcon;
};

const GOVERNANCE_BULLETS = [
    'Rules override machine learning',
    'Full audit trail',
    'Versioned policy packs',
    'No client data used for training'
];

const FLOW_STEPS: FlowStep[] = [
    {
        title: 'Upload borrower data (Excel/API)',
        detail: 'Ingest borrower files through spreadsheet upload or integration endpoints.'
    },
    {
        title: 'Policy engine evaluates',
        detail: 'Rules are executed against affordability, identity, and document quality checks.'
    },
    {
        title: 'Decision and audit report generated',
        detail: 'Decision outputs are paired with policy rationale and a traceable audit record.'
    },
    {
        title: 'Officer review and override (if needed)',
        detail: 'Authorized staff can intervene with documented justification and retained history.'
    }
];

const ARCHITECTURE_LAYERS: ArchitectureLayer[] = [
    {
        title: 'Policy Engine',
        detail: 'Runs institutional policy packs with deterministic enforcement and explicit decision rationale.',
        icon: Scale
    },
    {
        title: 'Risk Module',
        detail: 'Calculates risk indicators from submitted borrower and transaction evidence within policy guardrails.',
        icon: ShieldCheck
    },
    {
        title: 'Audit Layer',
        detail: 'Captures timestamped decision events, overrides, and evidence references for governance review.',
        icon: ScrollText
    },
    {
        title: 'Access Control',
        detail: 'Applies organization-scoped roles across officers, reviewers, and administrators.',
        icon: UsersRound
    }
];

export default function LandingPage() {
    return (
        <div className="landing-page min-h-screen bg-background text-foreground relative overflow-hidden">
            <header className="relative z-10 border-b border-border px-6 md:px-10">
                <div className="landing-nav-surface max-w-6xl mx-auto h-[72px] px-4 md:px-6 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-2 min-w-0">
                        <img src="/logo.png" alt="Mifi Pro" className="h-10 w-auto object-contain shrink-0" />
                        <div className="min-w-0">
                            <p className="landing-brand-word text-[15px] font-bold tracking-[-0.01em] leading-none truncate">Mifi Pro</p>
                            <p className="landing-suite-label mt-0.5 text-xs uppercase tracking-[0.15em] leading-none truncate">Partner Console</p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                        <a
                            href="mailto:sales@mifipro.com?subject=Request%20Demo%20-%20Mifi%20Pro"
                            className="landing-primary-btn inline-flex items-center justify-center rounded-[10px] px-4 py-2 text-sm font-bold tracking-[0.01em] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/60 focus-visible:ring-offset-2"
                        >
                            Request Demo
                        </a>
                        <Link
                            to="/login"
                            className="landing-secondary-btn inline-flex items-center justify-center rounded-[10px] border border-border bg-card px-4 py-2 text-sm font-semibold text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/55 focus-visible:ring-offset-2"
                        >
                            Sign in
                        </Link>
                    </div>
                </div>
            </header>

            <main className="relative z-10 px-5 md:px-10 pb-16 pt-12 md:pt-16">
                <div className="max-w-6xl mx-auto space-y-16">
                    <section className="landing-hero-grid grid xl:grid-cols-[minmax(0,1.06fr)_minmax(340px,0.94fr)] gap-8 lg:gap-10 items-start">
                        <div>
                            <p className="text-xs uppercase tracking-[0.14em] font-semibold text-muted-foreground">
                                For MFI and SACCO credit operations
                            </p>
                            <h1 className="landing-hero-title mt-2 text-4xl md:text-[2.8rem] leading-[1.1] text-foreground">
                                Reduce credit risk with institutional policy enforcement and audit traceability.
                            </h1>
                            <p className="mt-4 max-w-2xl text-base md:text-[1.05rem] text-muted-foreground leading-7">
                                MiFi Pro standardizes underwriting through governance-led controls, enforces policy consistently across lending teams, preserves full audit traceability, and sustains decision speed without operational chaos.
                            </p>

                            <div className="mt-6 flex flex-wrap items-center gap-3">
                                <a
                                    href="mailto:sales@mifipro.com?subject=Request%20Demo%20-%20Mifi%20Pro"
                                    className="landing-primary-btn inline-flex items-center gap-2 rounded-[10px] px-5 py-3 text-sm font-bold tracking-[0.01em] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/60 focus-visible:ring-offset-2"
                                >
                                    Request Demo
                                    <ArrowRight size={16} />
                                </a>
                                <a
                                    href="#sample-assessment"
                                    className="landing-secondary-btn inline-flex items-center gap-2 rounded-[10px] border border-border bg-card px-5 py-3 text-sm font-semibold text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/55 focus-visible:ring-offset-2"
                                >
                                    View Sample Assessment
                                </a>
                                <a
                                    href="#how-it-works"
                                    className="landing-tertiary-link inline-flex items-center gap-1 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/55 rounded"
                                >
                                    See how it works
                                    <ChevronRight size={15} />
                                </a>
                            </div>

                            <p className="landing-trust-line mt-4 text-sm text-muted-foreground">
                                Built for regulated credit institutions.
                            </p>
                        </div>

                        <aside id="sample-assessment" className="landing-preview-card landing-panel rounded-xl border border-border bg-card p-4 md:p-5">
                            <div className="flex items-start justify-between gap-3">
                                <div>
                                    <p className="text-xs uppercase tracking-[0.11em] font-semibold text-muted-foreground">Decision Chamber Snapshot</p>
                                    <h2 className="mt-1 text-lg text-foreground">Assessment Decision Record</h2>
                                </div>
                                <span className="text-[10px] uppercase tracking-[0.08em] text-muted-foreground">Sample</span>
                            </div>
                            <p className="landing-panel-meta mt-2 text-xs text-muted-foreground">
                                DC-2026-0417 | Engine v2.3.1 | Policy Pack: MFI Standard v2
                            </p>

                            <div className="mt-3 rounded-[10px] border border-border bg-background p-3 space-y-3">
                                <div className="flex flex-wrap items-center gap-2">
                                    <span className="landing-status-chip landing-status-chip-approved">
                                        <span className="landing-status-dot landing-status-dot-approved" aria-hidden />
                                        Approved
                                    </span>
                                    <span className="landing-status-chip landing-status-chip-review">
                                        <span className="landing-status-dot landing-status-dot-review" aria-hidden />
                                        Review
                                    </span>
                                    <span className="landing-status-chip landing-status-chip-rejected">
                                        <span className="landing-status-dot landing-status-dot-rejected" aria-hidden />
                                        Rejected
                                    </span>
                                    <span className="ml-auto text-[11px] text-muted-foreground">2026-03-01 14:06 CAT</span>
                                </div>

                                <div className="flex items-center justify-between rounded-[10px] border border-border bg-card px-3 py-2">
                                    <div>
                                        <p className="landing-panel-label text-[10px] uppercase tracking-[0.08em]">Risk Band</p>
                                        <p className="mt-1 text-sm font-semibold text-foreground">Moderate Risk</p>
                                    </div>
                                    <span className="landing-risk-badge">R-2</span>
                                </div>

                                <div className="border-t border-border pt-3">
                                <section className="rounded-[10px] border border-border bg-card px-3 py-2">
                                    <p className="landing-panel-label text-[10px] uppercase tracking-[0.08em]">Rule Breakdown</p>
                                    <ul className="mt-2 text-sm">
                                        <li className="flex items-center justify-between gap-2 py-1 border-b border-border">
                                            <span className="text-foreground">Debt-to-income below policy threshold</span>
                                            <span className="landing-rule-pass">Pass</span>
                                        </li>
                                        <li className="flex items-center justify-between gap-2 py-1 border-b border-border">
                                            <span className="text-foreground">Income consistency over 90 days</span>
                                            <span className="landing-rule-pass">Pass</span>
                                        </li>
                                        <li className="flex items-center justify-between gap-2 py-1">
                                            <span className="text-foreground">Document completeness validation</span>
                                            <span className="landing-rule-review">Review</span>
                                        </li>
                                    </ul>
                                </section>
                                </div>

                                <div className="border-t border-border pt-3">
                                <section className="rounded-[10px] border border-border bg-card px-3 py-2">
                                    <p className="landing-panel-label text-[10px] uppercase tracking-[0.08em]">Audit Log Preview</p>
                                    <ul className="mt-1 text-[12px] text-muted-foreground">
                                        <li className="flex items-center justify-between gap-2 py-1 border-b border-border">
                                            <span>Policy evaluation completed</span>
                                            <span className="font-mono text-[11px]">14:04</span>
                                        </li>
                                        <li className="flex items-center justify-between gap-2 py-1 border-b border-border">
                                            <span>Rule override request submitted</span>
                                            <span className="font-mono text-[11px]">14:05</span>
                                        </li>
                                        <li className="flex items-center justify-between gap-2 py-1">
                                            <span>Final recommendation logged</span>
                                            <span className="font-mono text-[11px]">14:06</span>
                                        </li>
                                    </ul>
                                </section>
                                </div>
                            </div>
                        </aside>
                    </section>

                    <section className="landing-section-block">
                        <div className="mb-5">
                            <p className="text-xs uppercase tracking-[0.14em] font-semibold text-muted-foreground">Governance</p>
                            <h2 className="mt-2 text-2xl md:text-[2rem] text-foreground">Institutional-Grade Governance</h2>
                        </div>
                        <article className="landing-panel rounded-xl border border-border bg-card p-4 md:p-5">
                            <p className="text-sm text-muted-foreground">
                                Governance controls are enforced at the system level for regulated credit operations.
                            </p>
                            <ul className="mt-3 grid sm:grid-cols-2 gap-x-6 gap-y-2.5">
                                {GOVERNANCE_BULLETS.map((item) => (
                                    <li key={item} className="flex items-center gap-2.5 text-sm text-foreground">
                                        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-foreground/70" />
                                        <span>{item}</span>
                                    </li>
                                ))}
                            </ul>
                        </article>
                    </section>

                    <section className="landing-section-block">
                        <div className="mb-5">
                            <p className="text-xs uppercase tracking-[0.14em] font-semibold text-muted-foreground">Deployment and controls</p>
                            <h2 className="mt-2 text-2xl md:text-[2rem] text-foreground">System Architecture</h2>
                        </div>
                        <div className="grid sm:grid-cols-2 gap-3.5">
                            {ARCHITECTURE_LAYERS.map((layer) => {
                                const Icon = layer.icon;
                                return (
                                    <article key={layer.title} className="landing-panel landing-hover-surface rounded-xl border border-border bg-card p-4">
                                        <div className="w-9 h-9 rounded-[10px] border border-border bg-muted inline-flex items-center justify-center text-foreground">
                                            <Icon size={18} />
                                        </div>
                                        <h3 className="mt-3 text-[15px] text-foreground">{layer.title}</h3>
                                        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{layer.detail}</p>
                                    </article>
                                );
                            })}
                        </div>
                        <p className="mt-4 text-sm text-muted-foreground">
                            Built to scale across branch networks, adapt to local regulatory change, and support enterprise expansion without policy drift.
                        </p>
                    </section>

                    <section id="how-it-works" className="landing-section-block">
                        <div className="mb-5">
                            <p className="text-xs uppercase tracking-[0.14em] font-semibold text-muted-foreground">Operations flow</p>
                            <h2 className="mt-2 text-2xl md:text-[2rem] text-foreground">How it works</h2>
                        </div>

                        <div className="grid md:grid-cols-4 gap-3.5">
                            {FLOW_STEPS.map((step, index) => (
                                <article key={step.title} className="landing-flow-step landing-panel rounded-xl border border-border bg-card p-4">
                                    <div className="w-8 h-8 rounded-full border border-border bg-muted text-sm font-semibold inline-flex items-center justify-center text-foreground">
                                        {index + 1}
                                    </div>
                                    <h3 className="mt-3 text-[15px] leading-snug text-foreground">{step.title}</h3>
                                    <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{step.detail}</p>
                                </article>
                            ))}
                        </div>
                    </section>
                </div>
            </main>

            <footer className="landing-footer relative z-10 border-t border-border bg-card">
                <div className="max-w-6xl mx-auto px-5 md:px-10 py-6 grid md:grid-cols-4 gap-4">
                    <div>
                        <p className="text-sm font-semibold text-foreground">Security</p>
                        <p className="mt-1 text-xs text-muted-foreground">No model training on client data.</p>
                    </div>
                    <div>
                        <p className="text-sm font-semibold text-foreground">Data Ownership</p>
                        <p className="mt-1 text-xs text-muted-foreground">Institutions retain ownership and control of all submitted records.</p>
                    </div>
                    <div>
                        <p className="text-sm font-semibold text-foreground">Enterprise Onboarding</p>
                        <a className="mt-1 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground" href="mailto:enterprise@mifipro.com?subject=Enterprise%20Onboarding">
                            enterprise@mifipro.com
                            <ArrowRight size={12} />
                        </a>
                    </div>
                    <div>
                        <p className="text-sm font-semibold text-foreground">Reliability</p>
                        <p className="mt-1 text-xs text-muted-foreground">System status placeholder: 99.9% uptime target.</p>
                    </div>
                </div>
            </footer>
        </div>
    );
}
