/**
 * QA Generator — Tailwind design system preset
 * Source: qa-generator-design-system (Claude Design handoff)
 *
 * Wired as a preset in tailwind.config.ts — do not edit tokens here;
 * edit them in src/styles/qa-tokens.css instead.
 */

/** @type {import('tailwindcss').Config} */
export default {
  theme: {
    extend: {
      colors: {
        base:      "var(--bg-base)",
        app:       "var(--bg-app)",
        panel:     "var(--bg-panel)",
        card:      "var(--bg-card)",
        "card-hi": "var(--bg-card-hi)",
        input:     "var(--bg-input)",

        fg: {
          1:       "var(--fg-1)",
          2:       "var(--fg-2)",
          3:       "var(--fg-3)",
          4:       "var(--fg-4)",
          inverse: "var(--fg-inverse)",
        },

        brand: {
          DEFAULT:  "var(--brand)",
          soft:     "var(--brand-soft)",
          glow:     "var(--brand-glow)",
          "glow-lo":"var(--brand-glow-lo)",
        },

        ok: {
          DEFAULT: "var(--ok)",
          soft:    "var(--ok-soft)",
          border:  "var(--ok-border)",
        },
        warn: {
          DEFAULT: "var(--warn)",
          soft:    "var(--warn-soft)",
          border:  "var(--warn-border)",
        },
        danger: {
          DEFAULT: "var(--danger)",
          soft:    "var(--danger-soft)",
          border:  "var(--danger-border)",
        },
        info: {
          DEFAULT: "var(--info)",
          soft:    "var(--info-soft)",
        },
        "tag-tan": {
          DEFAULT: "var(--tag-tan)",
          soft:    "var(--tag-tan-soft)",
          border:  "var(--tag-tan-border)",
        },
      },

      borderColor: {
        subtle: "var(--border-subtle)",
        soft:   "var(--border-soft)",
        strong: "var(--border-strong)",
        focus:  "var(--border-focus)",
      },

      borderRadius: {
        md:    "var(--r-md)",
        lg:    "var(--r-lg)",
        xl:    "var(--r-xl)",
        "2xl": "var(--r-2xl)",
        full:  "var(--r-full)",
      },

      boxShadow: {
        card:          "var(--shadow-card)",
        pop:           "var(--shadow-pop)",
        focus:         "var(--shadow-focus)",
        "glow-brand":  "var(--glow-brand)",
        "glow-ok":     "var(--glow-ok)",
        "glow-danger": "var(--glow-danger)",
      },

      fontFamily: {
        sans: ["Geist", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["Geist Mono", "JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },

      fontSize: {
        12: ["0.75rem",   { lineHeight: "1.35" }],
        13: ["0.8125rem", { lineHeight: "1.4"  }],
        14: ["0.875rem",  { lineHeight: "1.5"  }],
        15: ["0.9375rem", { lineHeight: "1.5"  }],
        16: ["1rem",      { lineHeight: "1.5"  }],
        18: ["1.125rem",  { lineHeight: "1.35" }],
        20: ["1.25rem",   { lineHeight: "1.35" }],
        24: ["1.5rem",    { lineHeight: "1.15" }],
        32: ["2rem",      { lineHeight: "1.05", letterSpacing: "-0.02em" }],
        40: ["2.5rem",    { lineHeight: "1.05", letterSpacing: "-0.02em" }],
      },

      letterSpacing: {
        tight:  "var(--ls-tight)",
        snug:   "var(--ls-snug)",
        wide:   "var(--ls-wide)",
        widest: "var(--ls-widest)",
      },

      spacing: {
        "sp-1": "4px",  "sp-2": "8px",  "sp-3": "12px", "sp-4": "16px",
        "sp-5": "20px", "sp-6": "24px", "sp-8": "32px", "sp-10": "40px",
        "sp-12": "48px","sp-16": "64px",
      },

      transitionTimingFunction: {
        "out-soft":    "cubic-bezier(0.22, 1, 0.36, 1)",
        "in-out-soft": "cubic-bezier(0.65, 0, 0.35, 1)",
      },

      transitionDuration: {
        fast: "120ms",
        base: "180ms",
        slow: "260ms",
      },

      keyframes: {
        fadeUp: {
          "0%":   { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)"   },
        },
        dsLivePulse: {
          "0%,100%": { opacity: "1"  },
          "50%":     { opacity: "0.4"},
        },
      },

      animation: {
        "fade-up":      "fadeUp 360ms cubic-bezier(0.22, 1, 0.36, 1) forwards",
        "ds-live-pulse":"dsLivePulse 1.8s cubic-bezier(0.65, 0, 0.35, 1) infinite",
      },

      backgroundImage: {
        "page-bloom":
          "radial-gradient(1200px 600px at 20% -10%, rgba(91,141,239,0.08), transparent 60%), " +
          "radial-gradient(900px 500px at 100% 100%, rgba(91,141,239,0.05), transparent 60%)",
        "brand-gradient": "linear-gradient(135deg, var(--brand) 0%, var(--brand-soft) 100%)",
      },
    },
  },
};
