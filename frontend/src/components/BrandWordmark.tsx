import React from 'react';

type BrandWordmarkProps = {
    className?: string;
    title?: string;
    showTagline?: boolean;
    showVersion?: boolean;
    surfaceColor?: string;
    tone?: 'dark' | 'light';
};

const DEFAULT_LAYOUT = {
    iX: 170,
    dotCx: 196,
    dotCy: 14,
    proX: 214,
    versionX: 343
};

export default function BrandWordmark({
    className,
    title = 'MIFI Pro',
    showTagline = true,
    showVersion = false,
    surfaceColor,
    tone = 'dark'
}: BrandWordmarkProps) {
    const uid = React.useId().replace(/:/g, '');
    const goldId = `mifi-gold-${uid}`;
    const textId = `mifi-text-${uid}`;
    const ruleId = `mifi-rule-${uid}`;
    const diamondId = `mifi-diamond-${uid}`;
    const auraId = `mifi-aura-${uid}`;
    const glowSmallId = `mifi-glow-small-${uid}`;
    const glowLargeId = `mifi-glow-large-${uid}`;
    const textShadowId = `mifi-text-shadow-${uid}`;
    const ecgGlowId = `mifi-ecg-glow-${uid}`;
    const viewBox = showTagline ? '0 0 580 130' : '0 8 580 94';
    const ecgPath = 'M 20,98 L 175,98 L 188,98 L 196,80 L 204,118 L 211,62 L 218,106 L 225,96 L 233,98 L 560,98';
    const resolvedSurfaceColor = surfaceColor ?? (tone === 'light' ? '#f8fafc' : '#0b1426');
    const textGradientStops =
        tone === 'light'
            ? { start: '#0f172a', end: '#334155' }
            : { start: '#ffffff', end: '#d8dde8' };
    const textShadow =
        tone === 'light'
            ? { dx: 0, dy: 1, blur: 1.8, color: '#ffffff', opacity: 0.58 }
            : { dx: 0, dy: 2, blur: 3, color: '#000000', opacity: 0.42 };
    const taglineColor = tone === 'light' ? '#64748b' : '#5B7195';

    const mifRef = React.useRef<SVGTextElement | null>(null);
    const iRef = React.useRef<SVGTextElement | null>(null);
    const proRef = React.useRef<SVGTextElement | null>(null);
    const [layout, setLayout] = React.useState(DEFAULT_LAYOUT);
    const [isReady, setIsReady] = React.useState(false);

    React.useEffect(() => {
        let isMounted = true;

        const positionWordmark = () => {
            if (!mifRef.current || !iRef.current || !proRef.current) return;

            try {
                const mifBox = mifRef.current.getBBox();
                const nextIX = mifBox.x + mifBox.width - 2;

                iRef.current.setAttribute('x', String(nextIX));
                const iBox = iRef.current.getBBox();

                const dotCy = iBox.y + iBox.height * 0.072;
                const dotCx = iBox.x + iBox.width * 0.46;

                proRef.current.setAttribute('x', String(iBox.x + iBox.width + 14));
                const proBox = proRef.current.getBBox();

                if (!isMounted) return;

                setLayout({
                    iX: nextIX,
                    dotCx,
                    dotCy,
                    proX: iBox.x + iBox.width + 14,
                    versionX: proBox.x + proBox.width - 22
                });
                setIsReady(true);
            } catch {
                if (isMounted) setIsReady(true);
            }
        };

        const schedulePosition = () => {
            window.requestAnimationFrame(() => {
                window.requestAnimationFrame(positionWordmark);
            });
        };

        schedulePosition();

        const fontSet = document.fonts;
        fontSet?.ready.then(schedulePosition).catch(() => undefined);

        const timeoutId = window.setTimeout(schedulePosition, 800);
        window.addEventListener('resize', schedulePosition);

        return () => {
            isMounted = false;
            window.clearTimeout(timeoutId);
            window.removeEventListener('resize', schedulePosition);
        };
    }, []);

    return (
        <svg
            viewBox={viewBox}
            className={className}
            role="img"
            aria-label={title}
            preserveAspectRatio="xMinYMid meet"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            style={{ visibility: isReady ? 'visible' : 'hidden' }}
        >
            <defs>
                <linearGradient id={goldId} x1="0" y1="0" x2="580" y2="130" gradientUnits="userSpaceOnUse">
                    <stop offset="0%" stopColor="#C9A84C" />
                    <stop offset="50%" stopColor="#EDD678" />
                    <stop offset="100%" stopColor="#C9A84C" />
                </linearGradient>
                <linearGradient id={textId} x1="0" y1="0" x2="0" y2="90" gradientUnits="userSpaceOnUse">
                    <stop offset="0%" stopColor={textGradientStops.start} />
                    <stop offset="100%" stopColor={textGradientStops.end} />
                </linearGradient>
                <linearGradient id={ruleId} x1="0" y1="0" x2="580" y2="0" gradientUnits="userSpaceOnUse">
                    <stop offset="0%" stopColor="#C9A84C" stopOpacity="0" />
                    <stop offset="14%" stopColor="#C9A84C" stopOpacity="0.72" />
                    <stop offset="56%" stopColor="#EDD678" stopOpacity="0.54" />
                    <stop offset="100%" stopColor="#EDD678" stopOpacity="0" />
                </linearGradient>
                <radialGradient id={diamondId} cx="50%" cy="35%" r="60%">
                    <stop offset="0%" stopColor="#FFF5CC" />
                    <stop offset="42%" stopColor="#EDD678" />
                    <stop offset="100%" stopColor="#C9A84C" />
                </radialGradient>
                <radialGradient id={auraId} cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stopColor="#C9A84C" stopOpacity="0.34" />
                    <stop offset="100%" stopColor="#C9A84C" stopOpacity="0" />
                </radialGradient>
                <filter id={glowSmallId} x="-60%" y="-60%" width="220%" height="220%">
                    <feGaussianBlur stdDeviation="2.4" result="blur" />
                    <feMerge>
                        <feMergeNode in="blur" />
                        <feMergeNode in="SourceGraphic" />
                    </feMerge>
                </filter>
                <filter id={glowLargeId} x="-90%" y="-90%" width="280%" height="280%">
                    <feGaussianBlur stdDeviation="6" result="blur" />
                    <feMerge>
                        <feMergeNode in="blur" />
                        <feMergeNode in="SourceGraphic" />
                    </feMerge>
                </filter>
                <filter id={textShadowId} x="-5%" y="-10%" width="110%" height="130%">
                    <feDropShadow
                        dx={textShadow.dx}
                        dy={textShadow.dy}
                        stdDeviation={textShadow.blur}
                        floodColor={textShadow.color}
                        floodOpacity={textShadow.opacity}
                    />
                </filter>
                <filter id={ecgGlowId} x="-5%" y="-300%" width="110%" height="700%">
                    <feGaussianBlur stdDeviation="2.3" result="blur" />
                    <feColorMatrix
                        in="blur"
                        type="matrix"
                        values="1 0.8 0 0 0 0.8 0.62 0 0 0 0 0 0 0 0 0 0 0 1 0"
                        result="colored"
                    />
                    <feMerge>
                        <feMergeNode in="colored" />
                        <feMergeNode in="SourceGraphic" />
                    </feMerge>
                </filter>
            </defs>

            <rect x="4" y="30" width="2" height="58" rx="1" fill={`url(#${goldId})`} opacity="0.34" />
            <rect
                x="4"
                y="30"
                width="2"
                height="58"
                rx="1"
                fill={`url(#${goldId})`}
                opacity="0.22"
                filter={`url(#${glowSmallId})`}
            />
            <rect x="0" y="40" width="10" height="1" rx="0.5" fill={`url(#${goldId})`} opacity="0.3" />
            <rect x="0" y="59" width="10" height="1" rx="0.5" fill={`url(#${goldId})`} opacity="0.3" />
            <rect x="0" y="78" width="10" height="1" rx="0.5" fill={`url(#${goldId})`} opacity="0.3" />

            <text
                ref={mifRef}
                x="20"
                y="86"
                fontFamily="'Playfair Display', serif"
                fontWeight="900"
                fontSize="90"
                letterSpacing="-2.5"
                fill={`url(#${textId})`}
                filter={`url(#${textShadowId})`}
            >
                MIF
            </text>
            <text
                ref={iRef}
                x={layout.iX}
                y="86"
                fontFamily="'Playfair Display', serif"
                fontWeight="900"
                fontSize="90"
                fill={`url(#${textId})`}
                filter={`url(#${textShadowId})`}
            >
                i
            </text>

            <circle cx={layout.dotCx} cy={layout.dotCy} r="9" fill={resolvedSurfaceColor} />

            <g transform={`translate(${layout.dotCx}, ${layout.dotCy})`}>
                <circle r="18" fill={`url(#${auraId})`} opacity="0.34">
                    <animate attributeName="opacity" values="0.26;0.44;0.26" dur="2.4s" repeatCount="indefinite" />
                    <animate attributeName="r" values="16;19;16" dur="2.4s" repeatCount="indefinite" />
                </circle>
                <circle r="9.5" fill={`url(#${goldId})`} opacity="0.22" filter={`url(#${glowLargeId})`}>
                    <animate attributeName="opacity" values="0.18;0.3;0.18" dur="2.4s" repeatCount="indefinite" />
                </circle>
                <rect
                    x="-9"
                    y="-9"
                    width="18"
                    height="18"
                    rx="0.5"
                    transform="rotate(45)"
                    fill={`url(#${goldId})`}
                    opacity="0.18"
                    filter={`url(#${glowLargeId})`}
                >
                    <animate attributeName="opacity" values="0.16;0.3;0.16" dur="2.4s" repeatCount="indefinite" />
                </rect>
                <rect
                    x="-7"
                    y="-7"
                    width="14"
                    height="14"
                    rx="0.3"
                    transform="rotate(45)"
                    fill="none"
                    stroke={`url(#${goldId})`}
                    strokeWidth="0.8"
                    opacity="0.42"
                />
                <rect
                    x="-5.5"
                    y="-5.5"
                    width="11"
                    height="11"
                    transform="rotate(45)"
                    fill={`url(#${diamondId})`}
                    filter={`url(#${glowSmallId})`}
                >
                    <animate attributeName="opacity" values="0.92;1;0.92" dur="2.4s" repeatCount="indefinite" />
                </rect>
                <rect x="-2.8" y="-2.8" width="5.6" height="5.6" transform="rotate(45)" fill="#FFFFFF" opacity="0.55" />
                <circle r="1.35" fill="#FFFFFF" opacity="0.96">
                    <animate attributeName="opacity" values="0.7;1;0.7" dur="2.4s" repeatCount="indefinite" />
                </circle>
                <line x1="0" y1="-9" x2="0" y2="-13" stroke={`url(#${goldId})`} strokeWidth="0.6" opacity="0.5" strokeLinecap="round" />
                <line x1="0" y1="9" x2="0" y2="13" stroke={`url(#${goldId})`} strokeWidth="0.6" opacity="0.5" strokeLinecap="round" />
                <line x1="-9" y1="0" x2="-13" y2="0" stroke={`url(#${goldId})`} strokeWidth="0.6" opacity="0.5" strokeLinecap="round" />
                <line x1="9" y1="0" x2="13" y2="0" stroke={`url(#${goldId})`} strokeWidth="0.6" opacity="0.5" strokeLinecap="round" />
                <circle r="2.2" fill="#FFF3B0" opacity="0.26" filter={`url(#${glowSmallId})`}>
                    <animate attributeName="opacity" values="0.22;0.72;0.22" dur="2.4s" repeatCount="indefinite" />
                    <animate attributeName="r" values="1.4;2.6;1.4" dur="2.4s" repeatCount="indefinite" />
                </circle>
            </g>

            <text
                ref={proRef}
                x={layout.proX}
                y="86"
                fontFamily="'DM Sans', sans-serif"
                fontWeight="200"
                fontSize="82"
                letterSpacing="1"
                fill={`url(#${goldId})`}
            >
                Pro
            </text>

            {showVersion ? (
                <text
                    x={layout.versionX}
                    y="30"
                    fontFamily="'DM Sans', sans-serif"
                    fontWeight="600"
                    fontSize="8"
                    letterSpacing="1.5"
                    fill="#C9A84C"
                    opacity="0.55"
                >
                    v3.0
                </text>
            ) : null}

            <line x1="20" y1="98" x2="560" y2="98" stroke={`url(#${ruleId})`} strokeWidth="0.5" opacity="0.24" />
            <path d={ecgPath} stroke={`url(#${ruleId})`} strokeWidth="0.6" fill="none" opacity="0.18" />
            <path
                d={ecgPath}
                stroke={`url(#${goldId})`}
                strokeOpacity="0.95"
                strokeWidth="1.55"
                fill="none"
                filter={`url(#${ecgGlowId})`}
                pathLength="900"
                strokeDasharray="900"
                strokeDashoffset="900"
            >
                <animate attributeName="stroke-dashoffset" values="900;0" dur="2.8s" repeatCount="indefinite" />
            </path>
            <circle cx="211" cy="62" r="2.7" fill="#F5E080" opacity="0" filter={`url(#${glowSmallId})`}>
                <animate attributeName="opacity" values="0;0;0;1;0" dur="2.8s" repeatCount="indefinite" begin="1.35s" />
                <animate attributeName="r" values="2.7;4.8;2.7" dur="2.8s" repeatCount="indefinite" begin="1.35s" />
            </circle>
            <circle r="2.9" fill="#F5E080" opacity="0" filter={`url(#${glowSmallId})`}>
                <animate attributeName="opacity" values="0;1;1;0" dur="2.8s" repeatCount="indefinite" />
                <animateMotion dur="2.8s" repeatCount="indefinite" path={ecgPath} />
            </circle>

            {showTagline ? (
                <text
                    x="20"
                    y="119"
                    fontFamily="'DM Sans', sans-serif"
                    fontWeight="600"
                    fontSize="10"
                    letterSpacing="5.1"
                    fill={taglineColor}
                >
                    {"LOAN OFFICER AI \u25C6 ZAMBIA"}
                </text>
            ) : null}

            <path d="M 14,18 L 14,10 L 22,10" stroke={`url(#${goldId})`} strokeWidth="0.8" opacity="0.3" strokeLinecap="round" />
            <path d="M 574,18 L 574,10 L 566,10" stroke={`url(#${goldId})`} strokeWidth="0.8" opacity="0.3" strokeLinecap="round" />
            <path d="M 14,112 L 14,120 L 22,120" stroke={`url(#${goldId})`} strokeWidth="0.8" opacity="0.3" strokeLinecap="round" />
            <path d="M 574,112 L 574,120 L 566,120" stroke={`url(#${goldId})`} strokeWidth="0.8" opacity="0.3" strokeLinecap="round" />
        </svg>
    );
}
