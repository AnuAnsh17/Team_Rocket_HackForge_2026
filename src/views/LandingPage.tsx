import React from 'react';
import {
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  FileSearch,
  Scale,
  CreditCard,
  Lock,
  Layers,
  Sparkles,
  ChevronRight,
  Zap,
  BarChart3,
  Building,
} from 'lucide-react';
import { ActiveTab } from '../types';
import { HeroReceiptScene } from '../components/three/HeroReceiptScene';
import { Mini3DScene } from '../components/three/Mini3DScene';

interface LandingPageProps {
  onNavigate: (tab: ActiveTab) => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onNavigate }) => {
  return (
    <div className="space-y-16 pb-16 text-slate-900">
      {/* 1. HERO SECTION WITH 3D FLOATING RECEIPT */}
      <section className="relative pt-4 pb-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          {/* Left Hero Column (Text & CTAs) */}
          <div className="lg:col-span-6 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-slate-100 border border-slate-200 rounded-full text-xs text-slate-700">
              <span className="flex h-2 w-2 rounded-full bg-emerald-500" />
              <span className="font-semibold">Proofline Engine v2026.4</span>
              <span className="text-slate-400">·</span>
              <span className="text-slate-500">Autonomous Evidence Verification</span>
            </div>

            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-slate-900 leading-[1.15]">
              Evidence-First AI Expense Auditing & Policy Compliance
            </h1>

            <p className="text-sm sm:text-base text-slate-600 leading-relaxed max-w-xl">
              Turn messy receipts into accurate, explainable reimbursement decisions.
              Proofline connects multimodal OCR line items to exact policy clauses,
              cumulative allowance caps, and perceptual duplicate detection.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <button
                onClick={() => onNavigate('overview')}
                className="flex items-center gap-2 px-5 py-3 text-sm font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded-lg transition-colors shadow-xs"
              >
                <span>Launch Audit Console</span>
                <ArrowRight className="h-4 w-4" />
              </button>

              <button
                onClick={() => onNavigate('workbench')}
                className="flex items-center gap-2 px-4 py-3 text-sm font-semibold text-slate-800 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg transition-colors"
              >
                <span>Receipt Workbench</span>
                <ChevronRight className="h-4 w-4 text-slate-400" />
              </button>
            </div>

            {/* Quick Metrics Strip */}
            <div className="grid grid-cols-3 gap-4 pt-6 border-t border-slate-200 max-w-lg">
              <div>
                <div className="font-mono text-xl font-bold text-slate-900">
                  ₹14.25L
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  Audited This Cycle
                </div>
              </div>
              <div>
                <div className="font-mono text-xl font-bold text-emerald-700">
                  99.8%
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  OCR Arithmetic Match
                </div>
              </div>
              <div>
                <div className="font-mono text-xl font-bold text-slate-900">
                  3-Valued
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  PASS / UNKNOWN / FAIL
                </div>
              </div>
            </div>
          </div>

          {/* Right Hero Column: 3D Floating Receipt Scene */}
          <div className="lg:col-span-6 bg-gradient-to-b from-slate-100/60 to-white rounded-2xl border border-slate-200/90 shadow-xs p-2 relative overflow-hidden">
            <HeroReceiptScene />
          </div>
        </div>
      </section>

      {/* 2. HOW IT WORKS SECTION (3 STEP 3D CARDS) */}
      <section className="space-y-6">
        <div className="text-center max-w-2xl mx-auto space-y-1.5">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Automated Audit Workflow
          </span>
          <h2 className="text-2xl font-bold text-slate-900">
            How Proofline Verifies Every Expense
          </h2>
          <p className="text-xs text-slate-500">
            Three rigorous stages connecting source pixels to policy clause citations and bank disbursements.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Step 1: 3D Scanning Scene */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3 shadow-2xs hover:shadow-xs transition-shadow flex flex-col justify-between">
            <div>
              <div className="bg-slate-50 rounded-lg border border-slate-100 overflow-hidden mb-3">
                <Mini3DScene type="scan" />
              </div>

              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-900 text-white">
                  01
                </span>
                <h3 className="text-sm font-bold text-slate-900">
                  Multimodal OCR & Extraction
                </h3>
              </div>
              <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                Extracts merchant GSTIN, transaction dates, itemized lines, and integrated taxes with arithmetic reconciliation across receipts and digital invoices.
              </p>
            </div>

            <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
              <span className="font-mono">Pixel-to-Field Mapping</span>
              <span className="text-emerald-700 font-medium">BBox Verified</span>
            </div>
          </div>

          {/* Step 2: 3D Policy Checking Scene */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3 shadow-2xs hover:shadow-xs transition-shadow flex flex-col justify-between">
            <div>
              <div className="bg-slate-50 rounded-lg border border-slate-100 overflow-hidden mb-3">
                <Mini3DScene type="policy" />
              </div>

              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-900 text-white">
                  02
                </span>
                <h3 className="text-sm font-bold text-slate-900">
                  Clause-Grounded Policy Verification
                </h3>
              </div>
              <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                Evaluates against city-tier lodging caps, cumulative daily meal limits, and prohibited items, citing exact policy clauses (e.g. Clause 4.2).
              </p>
            </div>

            <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
              <span className="font-mono">Cumulative Ledger</span>
              <span className="text-blue-700 font-medium">Rule Compiled</span>
            </div>
          </div>

          {/* Step 3: 3D Approval & Payout Scene */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3 shadow-2xs hover:shadow-xs transition-shadow flex flex-col justify-between">
            <div>
              <div className="bg-slate-50 rounded-lg border border-slate-100 overflow-hidden mb-3">
                <Mini3DScene type="approve" />
              </div>

              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-900 text-white">
                  03
                </span>
                <h3 className="text-sm font-bold text-slate-900">
                  Immutable Audit & Disbursement
                </h3>
              </div>
              <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                Records state transitions to a cryptographically sealed hash log and routes compliant items to automated payout disbursement via RazorpayX.
              </p>
            </div>

            <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
              <span className="font-mono">SOC-2 Type II Log</span>
              <span className="text-emerald-700 font-medium">Auto-Reimbursed</span>
            </div>
          </div>
        </div>
      </section>

      {/* 3. FOUR CORE CAPABILITIES GRID */}
      <section className="bg-white rounded-2xl border border-slate-200 p-8 shadow-xs space-y-6">
        <div className="max-w-xl">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Governance & Triage
          </span>
          <h2 className="text-xl font-bold text-slate-900 mt-1">
            Built for Enterprise Finance & HR Teams
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Designed to prevent fraudulent bleed while treating employees with transparency and dignity.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <div
            onClick={() => onNavigate('workbench')}
            className="cursor-pointer p-4 rounded-xl border border-slate-200 hover:border-slate-400 hover:bg-slate-50/50 transition-all group"
          >
            <div className="flex items-center justify-between text-slate-400 group-hover:text-slate-900">
              <FileSearch className="h-5 w-5" />
              <ChevronRight className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-bold text-slate-900 mt-3">
              Investigation Workbench
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Split-screen viewer with zoom, rotate, and OCR bounding boxes alongside arithmetic verification.
            </p>
          </div>

          <div
            onClick={() => onNavigate('duplicates')}
            className="cursor-pointer p-4 rounded-xl border border-slate-200 hover:border-slate-400 hover:bg-slate-50/50 transition-all group"
          >
            <div className="flex items-center justify-between text-slate-400 group-hover:text-slate-900">
              <Scale className="h-5 w-5" />
              <ChevronRight className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-bold text-slate-900 mt-3">
              Duplicate Review
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Perceptual image hash matching and side-by-side comparison without premature fraud accusations.
            </p>
          </div>

          <div
            onClick={() => onNavigate('policy-studio')}
            className="cursor-pointer p-4 rounded-xl border border-slate-200 hover:border-slate-400 hover:bg-slate-50/50 transition-all group"
          >
            <div className="flex items-center justify-between text-slate-400 group-hover:text-slate-900">
              <Layers className="h-5 w-5" />
              <ChevronRight className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-bold text-slate-900 mt-3">
              Policy Studio
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Drag-and-drop corporate PDF uploader compiling natural-language text into mathematical rules.
            </p>
          </div>

          <div
            onClick={() => onNavigate('audit-trail')}
            className="cursor-pointer p-4 rounded-xl border border-slate-200 hover:border-slate-400 hover:bg-slate-50/50 transition-all group"
          >
            <div className="flex items-center justify-between text-slate-400 group-hover:text-slate-900">
              <Lock className="h-5 w-5" />
              <ChevronRight className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-bold text-slate-900 mt-3">
              Audit Trail & Exports
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Immutable state changes and reviewer reasoning with CSV and PDF evidence pack export.
            </p>
          </div>
        </div>
      </section>

      {/* 4. BOTTOM ACTION CALLOUT */}
      <section className="bg-slate-900 text-white rounded-2xl p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold">
            <CheckCircle2 className="h-4 w-4" />
            <span>Ready for Review</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight">
            Explore the Live Proofline Enterprise Console
          </h2>
          <p className="text-xs text-slate-400 max-w-lg">
            Inspect pending receipts, test duplicate image hash matching, and evaluate cumulative allowance caps.
          </p>
        </div>

        <button
          onClick={() => onNavigate('overview')}
          className="flex items-center gap-2 px-5 py-3 text-xs font-semibold text-slate-900 bg-white hover:bg-slate-100 rounded-lg transition-colors whitespace-nowrap shadow-xs"
        >
          <span>Open Overview Dashboard</span>
          <ArrowRight className="h-4 w-4" />
        </button>
      </section>
    </div>
  );
};
