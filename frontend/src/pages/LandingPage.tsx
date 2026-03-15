import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import BrandWordmark from '../components/BrandWordmark';
import { api } from '../context/AuthContext';
import './LandingPage.css';

type FormState = {
    name: string;
    institution: string;
    phone: string;
    institutionType: string;
    volume: string;
};

type Stat = {
    target: number;
    suffix: string;
    label: string;
};

type LeadIntent = 'demo' | 'trial' | 'pilot' | 'contact';

type PricingPlan = {
    name: string;
    price: string;
    audience: string;
    features: string[];
    ctaLabel: string;
    action: 'modal' | 'login';
    intent?: LeadIntent;
    badge?: string;
};

type FaqItem = {
    question: string;
    answer: string;
};

const STATS: Stat[] = [
    { target: 60, suffix: 's', label: 'Seconds to assess a loan application' },
    { target: 100, suffix: '%', label: '% parsing accuracy on Zambian bank statements' },
    { target: 3, suffix: '×', label: 'More loans processed per officer per day' },
    { target: 0, suffix: '%', label: '% chance of decision being altered after sealing' }
];

const TRUST_ITEMS = ['Reads Zanaco statements', 'Sealed audit trail', 'No black box AI'];

const RULE_ITEMS = [
    { name: 'Debt-to-income below threshold', badge: 'PASS', badgeClass: 'badge-pass' },
    { name: 'Income consistency over 90 days', badge: 'PASS', badgeClass: 'badge-pass' },
    { name: 'Document completeness validation', badge: 'REVIEW', badgeClass: 'badge-review' }
];

const PROBLEMS = [
    {
        icon: '⏱️',
        title: 'Decisions take days, not minutes',
        description:
            'Loan officers manually read bank statements, calculate ratios by hand, and wait for committee meetings. Borrowers wait a week or more for a simple answer.'
    },
    {
        icon: '📊',
        title: 'No two officers decide the same way',
        description:
            'Without a structured system, decisions depend on mood, experience, and relationships. The same application gets different outcomes from different officers.'
    },
    {
        icon: '📋',
        title: 'No audit trail when things go wrong',
        description:
            'When a loan defaults and regulators ask why it was approved, there is no answer. Paper files get lost. Decisions cannot be reconstructed or defended.'
    },
    {
        icon: '📉',
        title: 'Default rates drain member savings',
        description:
            'A 16% default rate at a K500,000 lending pool means K80,000 lost — money that belongs to members. Bad decisions compound into bad portfolios.'
    },
    {
        icon: '🔒',
        title: 'Growth is capped by manual capacity',
        description:
            'One loan officer can only process so many applications per day by hand. Growing your portfolio means hiring more staff — more cost, more inconsistency.'
    },
    {
        icon: '🧾',
        title: 'Bank statements take an hour to read',
        description:
            'Manually reviewing 3 months of bank transactions to verify income and spot red flags takes a trained officer 45–60 minutes per application. Per application.'
    }
];

const STEPS = [
    {
        title: 'Upload applicant data via Excel',
        description:
            'Upload your existing client spreadsheet — any column format works. MIFI Pro automatically maps your columns to the required fields. No reformatting needed.'
    },
    {
        title: 'Upload bank statement & payslip',
        description:
            'MIFI Pro reads and parses Zambian bank statements automatically — extracting income, balances, spending patterns, and anomalies at 100% confidence in under 60 seconds.'
    },
    {
        title: 'Rules engine runs the assessment',
        description:
            'Your institutional policy rules evaluate the application — DTI ratios, income consistency, risk thresholds. The same rules apply to every application, every time.'
    },
    {
        title: 'AI explains the recommendation',
        description:
            'The Decision Copilot translates the rules verdict into plain language — exactly why the application passed or failed, which policies triggered, and what the officer should consider.'
    },
    {
        title: 'Officer makes the final decision',
        description:
            'The loan officer reviews the full assessment and approves, rejects, or refers. They seal the decision — generating an immutable audit record and a Credit Decision Summary PDF instantly.'
    }
];

const FEATURES = [
    {
        icon: '🏦',
        title: 'Zambian Bank Statement Parsing',
        description:
            'Reads Zanaco and other Zambian bank statements automatically at 100% extraction confidence. Income, balances, transaction patterns — extracted in seconds.'
    },
    {
        icon: '⚖️',
        title: 'Rules-Based Decision Engine',
        description:
            'Your lending policies enforced consistently on every single application. DTI ratios, income thresholds, risk bands — the same rules, every time, for every officer.'
    },
    {
        icon: '🤖',
        title: 'Decision Copilot AI',
        description:
            'The AI explains exactly why the recommendation was made — in plain language. Loan officers understand every decision. No black box. Full transparency.'
    },
    {
        icon: '🔒',
        title: 'Sealed Immutable Audit Trail',
        description:
            'Every sealed decision is permanently locked. Officer name, timestamp, policy version, risk score — all recorded. Decisions cannot be edited or deleted after sealing.'
    },
    {
        icon: '📊',
        title: 'Portfolio Overview & PAR Tracking',
        description:
            'Real-time portfolio health dashboard showing PAR 30/60/90, default rates, disbursed volume, and credit decision trends — all in one place.'
    },
    {
        icon: '📄',
        title: 'Credit Decision Summary PDF',
        description:
            'Every sealed decision automatically generates a formatted PDF — applicant details, risk score, policy triggers, and officer sign-off. Ready for your records instantly.'
    }
];

const AUDIENCES = [
    {
        icon: '🤝',
        title: 'SACCOs',
        description:
            'Small teams processing high loan volumes manually. MIFI Pro gives your loan committee structure, speed, and an audit trail without replacing how you work.'
    },
    {
        icon: '🏢',
        title: 'Microfinance Institutions',
        description:
            'MFIs that need consistent decisions across multiple officers and branches. Policy versioning ensures your entire team follows the same rules, always.'
    },
    {
        icon: '💼',
        title: 'Salary-Based Lenders',
        description:
            'Lenders servicing employed borrowers and government workers. Payslip parsing and standardized income assessment make your process fast and repeatable.'
    }
];

const PLATFORM_PLANS: PricingPlan[] = [
    {
        name: 'Starter',
        price: 'K600/mo',
        audience: 'SACCOs & small lenders — under 30 loans per month.',
        features: [
            '30 assessments/month',
            '2 loan officer seats',
            'Bank statement parsing',
            'Rules-based decision engine',
            'PDF Credit Decision Summary',
            'Sealed audit trail',
            'Email support'
        ],
        ctaLabel: 'Start Free Trial',
        action: 'modal',
        intent: 'trial'
    },
    {
        name: 'Standard',
        price: 'K1,800/mo',
        audience: 'Growing MFIs — more volume, more officers, full compliance tools.',
        features: [
            '100 assessments/month',
            '5 loan officer seats',
            'Everything in Starter',
            'Full compliance audit logs',
            'Policy Studio access',
            'Portfolio Overview dashboard',
            'PAR 30/60/90 tracking',
            'Priority support'
        ],
        ctaLabel: 'Start Free Trial',
        action: 'modal',
        intent: 'trial',
        badge: 'Most Popular'
    },
    {
        name: 'Growth',
        price: 'K4,500/mo',
        audience: 'Larger MFIs — high volumes, multiple branches or officers.',
        features: [
            'Unlimited assessments',
            'Unlimited officer seats',
            'Everything in Standard',
            'Decision Copilot AI',
            'Custom policy configuration',
            'Dedicated onboarding support',
            'SLA guarantee'
        ],
        ctaLabel: 'Contact Us',
        action: 'modal',
        intent: 'contact'
    }
];

const API_PLANS: PricingPlan[] = [
    {
        name: 'API Starter',
        price: 'K1,500/mo',
        audience: 'Up to 100 API calls/month',
        features: [
            'Full decision engine access',
            'Webhook support',
            'API key management',
            'JSON response format',
            'Developer documentation'
        ],
        ctaLabel: 'Get API Keys',
        action: 'login'
    },
    {
        name: 'API Standard',
        price: 'K3,500/mo',
        audience: 'Up to 500 API calls/month',
        features: [
            'Everything in API Starter',
            'Priority API support',
            'Custom callback URLs',
            'Audit log export',
            'SLA response time'
        ],
        ctaLabel: 'Get API Keys',
        action: 'login'
    },
    {
        name: 'API Enterprise',
        price: 'Custom',
        audience: 'Unlimited API calls',
        features: [
            'Dedicated infrastructure',
            'Uptime SLA guarantee',
            'Direct integration support',
            'Custom policy engine config',
            'White-label options'
        ],
        ctaLabel: 'Contact Us',
        action: 'modal',
        intent: 'contact'
    }
];

const FAQ_ITEMS: FaqItem[] = [
    {
        question: 'Can I switch plans later?',
        answer: 'Yes. You can move to a higher plan as your volume grows, and we keep your team setup and historical decisions intact.'
    },
    {
        question: 'What happens if I exceed my assessment limit?',
        answer: 'Additional assessments are billed at K15 each, and we notify you once you reach 80% of your monthly limit.'
    },
    {
        question: 'Do you support banks other than Zanaco?',
        answer: 'Yes. MIFI Pro supports Zanaco and other supported Zambian bank statement formats, with onboarding guidance for your institution.'
    },
    {
        question: 'Is my institution\'s data secure?',
        answer: 'Yes. Decisions are sealed with an audit trail, and platform access is controlled per institution and user role.'
    },
    {
        question: 'How does the free pilot work?',
        answer: 'Qualifying MFIs and SACCOs get up to 3 months free, 20 real assessments, setup help, and no automatic billing.'
    },
    {
        question: 'Can MIFI Pro integrate with our existing system?',
        answer: 'Yes. API plans include decision engine access, webhooks, JSON responses, and support for integration into existing loan systems.'
    }
];

const LEAD_COPY: Record<LeadIntent, { title: string; description: string; submitLabel: string; successTitle: string; successDescription: string }> = {
    demo: {
        title: 'Request a Demo',
        description: 'We\'ll reach out within 24 hours to schedule your free 15-minute walkthrough.',
        submitLabel: 'Book My Free Demo →',
        successTitle: 'Demo Requested!',
        successDescription: 'Thank you. We\'ll contact you on WhatsApp within 24 hours to schedule your free demo. Get ready to see MIFI Pro in action.'
    },
    trial: {
        title: 'Start Free Trial',
        description: 'Tell us a bit about your institution and we\'ll help you start your free trial on the right plan.',
        submitLabel: 'Start My Free Trial →',
        successTitle: 'Trial Request Received!',
        successDescription: 'Thanks. We\'ll contact you within 24 hours to activate your trial and help your team get started.'
    },
    pilot: {
        title: 'Apply for Free Pilot',
        description: 'Share your institution details and we\'ll review whether you qualify for the free 3-month pilot.',
        submitLabel: 'Apply for Free Pilot →',
        successTitle: 'Pilot Application Received!',
        successDescription: 'Thanks. We\'ll review your pilot request and contact you shortly with next steps.'
    },
    contact: {
        title: 'Contact MIFI Pro',
        description: 'Share your details and we\'ll reach out to discuss pricing, onboarding, or enterprise/API requirements.',
        submitLabel: 'Send My Request →',
        successTitle: 'Request Received!',
        successDescription: 'Thank you. Our team will reach out shortly to continue the conversation.'
    }
};

const INITIAL_FORM: FormState = {
    name: '',
    institution: '',
    phone: '',
    institutionType: '',
    volume: ''
};

function CheckIcon() {
    return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    );
}

export default function LandingPage() {
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [showSuccess, setShowSuccess] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [riskWidth, setRiskWidth] = useState('0%');
    const [formValues, setFormValues] = useState<FormState>(INITIAL_FORM);
    const [animatedStats, setAnimatedStats] = useState<number[]>(() => STATS.map(() => 0));
    const [leadIntent, setLeadIntent] = useState<LeadIntent>('demo');
    const [openFaq, setOpenFaq] = useState<number | null>(0);
    const statsRef = useRef<HTMLDivElement | null>(null);
    const resetTimerRef = useRef<number | null>(null);
    const activeLeadCopy = LEAD_COPY[leadIntent];

    useEffect(() => {
        const previousScrollBehavior = document.documentElement.style.scrollBehavior;
        document.documentElement.style.scrollBehavior = 'smooth';

        return () => {
            document.documentElement.style.scrollBehavior = previousScrollBehavior;
        };
    }, []);

    useEffect(() => {
        document.body.style.overflow = isModalOpen ? 'hidden' : '';

        return () => {
            document.body.style.overflow = '';
        };
    }, [isModalOpen]);

    useEffect(() => {
        const timer = window.setTimeout(() => {
            setRiskWidth('12%');
        }, 1000);

        return () => {
            window.clearTimeout(timer);
        };
    }, []);

    useEffect(() => {
        const statsElement = statsRef.current;

        if (!statsElement) {
            return undefined;
        }

        let frameId: number | null = null;
        let observer: IntersectionObserver | null = null;
        let hasAnimated = false;

        const animateCounters = () => {
            const duration = 2000;
            let startTime: number | null = null;

            const step = (timestamp: number) => {
                if (startTime === null) {
                    startTime = timestamp;
                }

                const progress = Math.min((timestamp - startTime) / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);

                setAnimatedStats(STATS.map((stat) => Math.floor(eased * stat.target)));

                if (progress < 1) {
                    frameId = window.requestAnimationFrame(step);
                } else {
                    setAnimatedStats(STATS.map((stat) => stat.target));
                }
            };

            frameId = window.requestAnimationFrame(step);
        };

        if ('IntersectionObserver' in window) {
            observer = new IntersectionObserver(
                (entries) => {
                    const hasVisibleEntry = entries.some((entry) => entry.isIntersecting);

                    if (hasVisibleEntry && !hasAnimated) {
                        hasAnimated = true;
                        animateCounters();
                        observer?.disconnect();
                    }
                },
                { threshold: 0.3 }
            );

            observer.observe(statsElement);
        } else {
            animateCounters();
        }

        return () => {
            observer?.disconnect();
            if (frameId !== null) {
                window.cancelAnimationFrame(frameId);
            }
        };
    }, []);

    useEffect(() => {
        return () => {
            if (resetTimerRef.current !== null) {
                window.clearTimeout(resetTimerRef.current);
            }
        };
    }, []);

    const openModal = (intent: LeadIntent = 'demo') => {
        if (resetTimerRef.current !== null) {
            window.clearTimeout(resetTimerRef.current);
            resetTimerRef.current = null;
        }

        setLeadIntent(intent);
        setShowSuccess(false);
        setIsModalOpen(true);
    };

    const closeModal = () => {
        setIsModalOpen(false);

        if (showSuccess) {
            resetTimerRef.current = window.setTimeout(() => {
                setShowSuccess(false);
                setFormValues(INITIAL_FORM);
                resetTimerRef.current = null;
            }, 300);
        }
    };

    const handleFieldChange =
        (field: keyof FormState) =>
        (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
            setFormValues((current) => ({ ...current, [field]: event.target.value }));
        };

    const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();

        if (!formValues.name.trim() || !formValues.institution.trim() || !formValues.phone.trim()) {
            toast.error('Please fill in your name, institution, and phone number.');
            return;
        }

        setIsSubmitting(true);
        try {
            await api.post('/lead-requests', {
                intent: leadIntent,
                name: formValues.name.trim(),
                institution: formValues.institution.trim(),
                phone: formValues.phone.trim(),
                institution_type: formValues.institutionType || undefined,
                volume: formValues.volume || undefined
            });
            setShowSuccess(true);
        } catch (error: any) {
            console.error('Failed to submit lead request', error);
            toast.error(error?.response?.data?.detail || 'We could not send your request right now. Please try again.');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="mifi-landing" id="top">
            <nav>
                <a className="logo" href="#top">
                    <BrandWordmark className="landing-wordmark" showTagline={false} />
                </a>
                <ul className="links">
                    <li><a href="#how">How It Works</a></li>
                    <li><a href="#features">Features</a></li>
                    <li><a href="#pricing">Pricing</a></li>
                    <li><a href="#who">Who It&apos;s For</a></li>
                </ul>
                <div className="nav-cta">
                    <Link className="btn-ghost" to="/login">Sign In</Link>
                    <button className="btn-primary" type="button" onClick={() => openModal('demo')}>Request Demo</button>
                </div>
            </nav>

            <section className="hero">
                <div className="hero-content">
                    <div className="hero-badge"><span></span>Built for Zambian MFIs &amp; SACCOs</div>
                    <h1>Credit decisions in <em>60 seconds.</em> Not 6 days.</h1>
                    <p className="hero-desc">
                        MIFI Pro gives your loan officers a rules-based decision engine that reads bank
                        statements automatically, enforces your lending policy, and generates a full audit
                        trail — every single time.
                    </p>
                    <div className="hero-actions">
                        <button className="btn-lg" type="button" onClick={() => openModal('demo')}>Request a Free Demo →</button>
                        <a className="btn-outline-lg" href="#how">See How It Works</a>
                    </div>
                    <div className="hero-trust">
                        {TRUST_ITEMS.map((item) => (
                            <div className="trust-item" key={item}><CheckIcon />{item}</div>
                        ))}
                    </div>
                </div>

                <div className="hero-visual">
                    <div className="float-card float-card-1">
                        <div className="float-label">Bank Statement</div>
                        <div className="float-value">100% ✓</div>
                        <div className="float-sub">Parsed · No anomalies</div>
                    </div>

                    <div className="decision-card">
                        <div className="card-header">
                            <span className="card-header-title">Decision Chamber</span>
                            <span className="status-pill status-pending">Pending Officer</span>
                        </div>
                        <div className="card-body">
                            <div className="card-meta">
                                <div className="meta-item"><label>Assessment ID</label><span className="meta-value">ASMT-DADA2B29</span></div>
                                <div className="meta-item"><label>Recommendation</label><span className="meta-value approve">APPROVE</span></div>
                                <div className="meta-item"><label>Risk Score</label><span className="meta-value">12.0%</span></div>
                                <div className="meta-item"><label>Risk Level</label><span className="meta-value low">LOW</span></div>
                            </div>
                            <div className="risk-bar-wrap">
                                <div className="risk-bar-label"><span>Risk Exposure</span><span className="risk-low-text">12% — Low</span></div>
                                <div className="risk-bar"><div className="risk-fill" style={{ width: riskWidth }}></div></div>
                            </div>
                            <div className="rules-list">
                                {RULE_ITEMS.map((rule) => (
                                    <div className="rule-item" key={rule.name}>
                                        <span className="rule-name">{rule.name}</span>
                                        <span className={`rule-badge ${rule.badgeClass}`}>{rule.badge}</span>
                                    </div>
                                ))}
                            </div>
                            <div className="decision-buttons">
                                <button className="dec-btn dec-approve" type="button">Approve</button>
                                <button className="dec-btn dec-reject" type="button">Reject</button>
                                <button className="dec-btn dec-refer" type="button">Refer</button>
                            </div>
                        </div>
                    </div>

                    <div className="float-card float-card-2">
                        <div className="float-label">Default Rate</div>
                        <div className="float-value">0.0%</div>
                        <div className="float-sub">Portfolio at Risk · PAR90</div>
                    </div>
                </div>
            </section>

            <div className="stats-bar" ref={statsRef}>
                {STATS.map((stat, index) => (
                    <div className="stat-item" key={stat.label}>
                        <span className="stat-num">{animatedStats[index]}{stat.suffix}</span>
                        <div className="stat-label">{stat.label}</div>
                    </div>
                ))}
            </div>

            <section className="section" id="problem">
                <div className="section-label">The Problem</div>
                <h2 className="section-title">Manual loan decisions are<br />costing your institution</h2>
                <p className="section-desc">Across Zambia&apos;s MFIs and SACCOs, loan officers process applications by hand — creating delays, inconsistencies, and defaults that grow your portfolio at risk every month.</p>
                <div className="problems-grid">
                    {PROBLEMS.map((problem) => (
                        <div className="problem-card" key={problem.title}>
                            <div className="problem-icon">{problem.icon}</div>
                            <div className="problem-title">{problem.title}</div>
                            <div className="problem-desc">{problem.description}</div>
                        </div>
                    ))}
                </div>
            </section>

            <section className="section how-section" id="how">
                <div className="section-label">How It Works</div>
                <h2 className="section-title">From document upload<br />to sealed decision in minutes</h2>
                <div className="how-grid spaced-grid">
                    <div className="steps">
                        {STEPS.map((step, index) => (
                            <div className="step" key={step.title}>
                                <div className="step-num">{index + 1}</div>
                                <div>
                                    <div className="step-title">{step.title}</div>
                                    <div className="step-desc">{step.description}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                    <div className="preview-box">
                        <div className="preview-header">
                            <div className="dot dot-red"></div>
                            <div className="dot dot-yellow"></div>
                            <div className="dot dot-green"></div>
                            <span className="preview-title">Document Insight — Bank Statement</span>
                        </div>
                        <div className="preview-content">
                            <div className="mini-label preview-top-label">Zanaco · 2025-11-04 to 2026-01-04</div>
                            <div className="bs-parsed">✓ Parsed · Confidence 100%</div>
                            <div className="preview-strong">Closing balance parsed at ZMW 1,623.18</div>
                            <div className="mini-label">AI Summary</div>
                            <div className="preview-note">Coverage period: 2025-11-04 to 2026-01-04 · Provider: Zanaco · All primary structured fields extracted successfully.</div>
                            <div className="extracted-fields">
                                <div className="field-box"><div className="field-label">Bank Name</div><div className="field-value">Zanaco</div></div>
                                <div className="field-box"><div className="field-label">Account Holder</div><div className="field-value">E. Bwanga</div></div>
                                <div className="field-box"><div className="field-label">Currency</div><div className="field-value">ZMW</div></div>
                                <div className="field-box"><div className="field-label">Closing Balance</div><div className="field-value green-text">1,623.18</div></div>
                            </div>
                            <div className="mini-label">Flags / Anomalies</div>
                            <div className="anomaly-none">✓ No anomalies flagged</div>
                        </div>
                    </div>
                </div>
            </section>

            <section className="section features-section" id="features">
                <div className="section-head-center">
                    <div className="section-label">Features</div>
                    <h2 className="section-title">Everything a loan officer needs.<br />Nothing they don&apos;t.</h2>
                </div>
                <div className="features-grid">
                    {FEATURES.map((feature) => (
                        <div className="feature-item" key={feature.title}>
                            <div className="feature-icon">{feature.icon}</div>
                            <div className="feature-title">{feature.title}</div>
                            <div className="feature-desc">{feature.description}</div>
                        </div>
                    ))}
                </div>
            </section>

            <section className="section" id="who">
                <div className="section-label">Who It&apos;s For</div>
                <h2 className="section-title">Built for regulated<br />credit institutions in Zambia</h2>
                <p className="section-desc">Whether you&apos;re a SACCO with 200 members or an MFI processing thousands of loans a month, MIFI Pro scales to your institution.</p>
                <div className="audience-grid">
                    {AUDIENCES.map((audience) => (
                        <div className="audience-card" key={audience.title}>
                            <div className="audience-icon">{audience.icon}</div>
                            <div className="audience-title">{audience.title}</div>
                            <div className="audience-desc">{audience.description}</div>
                        </div>
                    ))}
                </div>
            </section>

            <section className="section pricing-section" id="pricing">
                <div className="section-head-center">
                    <div className="section-label">Billing & Pricing</div>
                    <h2 className="section-title">Simple plans for lenders at every stage</h2>
                    <p className="section-desc pricing-intro">
                        Choose the plan that matches your current loan volume, team size, and compliance needs.
                    </p>
                </div>

                <div className="pricing-grid">
                    {PLATFORM_PLANS.map((plan) => (
                        <div className={`pricing-card ${plan.badge ? 'popular' : ''}`} key={plan.name}>
                            {plan.badge && <div className="pricing-badge">⭐ {plan.badge}</div>}
                            <div className="pricing-card-head">
                                <div className="pricing-name">{plan.name}</div>
                                <div className="pricing-price">{plan.price}</div>
                                {plan.price !== 'Custom' && (
                                    <div className="pricing-billing-meta">
                                        <span>Billed monthly</span>
                                        <span>Cancel anytime</span>
                                    </div>
                                )}
                                <p className="pricing-audience">{plan.audience}</p>
                            </div>
                            <ul className="pricing-feature-list">
                                {plan.features.map((feature) => (
                                    <li className="pricing-feature" key={feature}>
                                        <CheckIcon />
                                        <span>{feature}</span>
                                    </li>
                                ))}
                            </ul>
                            {plan.action === 'login' ? (
                                <Link className="pricing-action" to="/login">{plan.ctaLabel}</Link>
                            ) : (
                                <button className="pricing-action" type="button" onClick={() => openModal(plan.intent ?? 'demo')}>
                                    {plan.ctaLabel}
                                </button>
                            )}
                        </div>
                    ))}
                </div>

                <div className="pricing-note">
                    Need more than your plan includes? Additional assessments are billed at K15 each. You&apos;ll be notified at 80% of your monthly limit.
                </div>

                <div className="section-head-center api-head">
                    <div className="section-label">API Access</div>
                    <h3 className="pricing-subtitle">Integrate into your existing system</h3>
                    <p className="section-desc pricing-intro">
                        Already have a core banking or loan management system? Plug MIFI Pro&apos;s decision engine in via API.
                    </p>
                </div>

                <div className="pricing-grid api-grid">
                    {API_PLANS.map((plan) => (
                        <div className="pricing-card api-card" key={plan.name}>
                            <div className="pricing-card-head">
                                <div className="pricing-name">{plan.name}</div>
                                <div className="pricing-price">{plan.price}</div>
                                {plan.price !== 'Custom' && (
                                    <div className="pricing-billing-meta">
                                        <span>Billed monthly</span>
                                        <span>Cancel anytime</span>
                                    </div>
                                )}
                                <p className="pricing-audience">{plan.audience}</p>
                            </div>
                            <ul className="pricing-feature-list">
                                {plan.features.map((feature) => (
                                    <li className="pricing-feature" key={feature}>
                                        <CheckIcon />
                                        <span>{feature}</span>
                                    </li>
                                ))}
                            </ul>
                            {plan.action === 'login' ? (
                                <Link className="pricing-action pricing-action-secondary" to="/login">{plan.ctaLabel}</Link>
                            ) : (
                                <button
                                    className="pricing-action pricing-action-secondary"
                                    type="button"
                                    onClick={() => openModal(plan.intent ?? 'contact')}
                                >
                                    {plan.ctaLabel}
                                </button>
                            )}
                        </div>
                    ))}
                </div>

                <div className="pilot-banner">
                    <div className="pilot-copy">
                        <div className="pilot-badge">🔒 Limited Spots Available</div>
                        <h3 className="pricing-subtitle">Not ready to commit? Start with a free pilot.</h3>
                        <p className="pricing-intro pilot-text">
                            We offer qualifying MFIs and SACCOs 3 months of completely free access — no credit card, no contract. Just 20 real loan assessments and honest feedback from your team.
                        </p>
                        <ul className="pilot-list">
                            <li><CheckIcon /><span>Full platform — no feature limits</span></li>
                            <li><CheckIcon /><span>3 months completely free</span></li>
                            <li><CheckIcon /><span>We help you get set up</span></li>
                            <li><CheckIcon /><span>No automatic billing ever</span></li>
                        </ul>
                    </div>
                    <button className="pricing-action" type="button" onClick={() => openModal('pilot')}>
                        Apply for Free Pilot →
                    </button>
                </div>

                <div className="faq-block">
                    <div className="section-head-center">
                        <div className="section-label">FAQ</div>
                        <h3 className="pricing-subtitle">Common questions</h3>
                    </div>
                    <div className="faq-list">
                        {FAQ_ITEMS.map((item, index) => {
                            const isOpen = openFaq === index;
                            return (
                                <div className={`faq-item ${isOpen ? 'open' : ''}`} key={item.question}>
                                    <button
                                        className="faq-question"
                                        type="button"
                                        aria-expanded={isOpen}
                                        onClick={() => setOpenFaq(isOpen ? null : index)}
                                    >
                                        <span>{item.question}</span>
                                        <span className="faq-symbol">{isOpen ? '−' : '+'}</span>
                                    </button>
                                    {isOpen && <p className="faq-answer">{item.answer}</p>}
                                </div>
                            );
                        })}
                    </div>
                </div>
            </section>

            <section className="cta-section">
                <div className="section-label">Get Started</div>
                <h2 className="cta-title">Ready to transform how your<br />institution makes loan decisions?</h2>
                <p className="cta-desc">Join Zambian lending institutions already using MIFI Pro. Free 3-month pilot for qualifying MFIs and SACCOs.</p>
                <div className="cta-actions">
                    <button className="btn-lg" type="button" onClick={() => openModal('demo')}>Request a Free Demo →</button>
                    <button className="btn-outline-lg" type="button" onClick={() => openModal('contact')}>Contact Us Directly</button>
                </div>
                <div className="cta-note">No contracts. No credit card. Just a 15-minute demo and 3 months free.</div>
            </section>

            <footer>
                <div className="footer-copy">© 2026 MIFI Pro. Built for regulated credit institutions in Zambia.</div>
                <div className="footer-links">
                    <a href="#top">Privacy Policy</a>
                    <a href="#top">Terms of Service</a>
                    <a href="mailto:admin@mifipro.com">Contact</a>
                </div>
            </footer>

            <div className={`modal-overlay ${isModalOpen ? 'open' : ''}`} aria-hidden={!isModalOpen} onClick={closeModal}>
                <div className="modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
                    <button className="modal-close" aria-label="Close modal" type="button" onClick={closeModal}>✕</button>
                    {!showSuccess ? (
                        <form onSubmit={handleSubmit}>
                            <div className="modal-title">{activeLeadCopy.title}</div>
                            <div className="modal-desc">{activeLeadCopy.description}</div>
                            <div className="form-group"><label htmlFor="fname">Your Full Name</label><input id="fname" type="text" placeholder="e.g. John Mwansa" value={formValues.name} onChange={handleFieldChange('name')} /></div>
                            <div className="form-group"><label htmlFor="finst">Institution Name</label><input id="finst" type="text" placeholder="e.g. Lusaka Teachers SACCO" value={formValues.institution} onChange={handleFieldChange('institution')} /></div>
                            <div className="form-group"><label htmlFor="fphone">WhatsApp / Phone Number</label><input id="fphone" type="tel" placeholder="e.g. 0978 123 456" value={formValues.phone} onChange={handleFieldChange('phone')} /></div>
                            <div className="form-group"><label htmlFor="ftype">Institution Type</label><select id="ftype" value={formValues.institutionType} onChange={handleFieldChange('institutionType')}><option value="">Select type...</option><option value="SACCO">SACCO</option><option value="Microfinance Institution (MFI)">Microfinance Institution (MFI)</option><option value="Salary-Based Lender">Salary-Based Lender</option><option value="Other">Other</option></select></div>
                            <div className="form-group"><label htmlFor="fvolume">Loans processed per month</label><select id="fvolume" value={formValues.volume} onChange={handleFieldChange('volume')}><option value="">Select range...</option><option value="Under 50">Under 50</option><option value="50 – 200">50 – 200</option><option value="200 – 500">200 – 500</option><option value="500+">500+</option></select></div>
                            <button className="form-submit" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Sending...' : activeLeadCopy.submitLabel}</button>
                        </form>
                    ) : (
                        <div className="success-msg">
                            <div className="success-icon">✅</div>
                            <div className="success-title">{activeLeadCopy.successTitle}</div>
                            <div className="success-desc">{activeLeadCopy.successDescription}</div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
