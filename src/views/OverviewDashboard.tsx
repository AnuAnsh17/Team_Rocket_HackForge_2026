import React, { useState } from 'react';
import {
  TrendingUp,
  AlertCircle,
  FileX,
  Copy,
  Clock,
  CheckCircle2,
  ArrowRight,
  ShieldAlert,
  ChevronRight,
  Filter,
} from 'lucide-react';
import { Claim, ActiveTab } from '../types';
import { ComplianceHeatmap } from '../components/ComplianceHeatmap';

interface OverviewDashboardProps {
  claims: Claim[];
  onNavigate: (tab: ActiveTab) => void;
  onFilterQueue: (filter: string) => void;
  onSelectClaim: (claimId: string) => void;
}

export const OverviewDashboard: React.FC<OverviewDashboardProps> = ({
  claims,
  onNavigate,
  onFilterQueue,
  onSelectClaim,
}) => {
  const [hoveredDonut, setHoveredDonut] = useState<string | null>(null);

  const kpis = [
    {
      id: 'all',
      title: 'Total Submitted',
      value: '₹14,25,000',
      subtitle: '48 total submissions this cycle',
      filterTarget: 'All',
      trend: '+12.4% vs last mo',
      trendPositive: true,
      icon: TrendingUp,
      accentBorder: 'hover:border-slate-400',
    },
    {
      id: 'pending',
      title: 'Awaiting Reimbursement',
      value: '₹3,80,000',
      subtitle: '22 approved payout claims',
      filterTarget: 'Pending Approval',
      trend: 'Avg 2.4 days payout cycle',
      trendPositive: true,
      icon: Clock,
      accentBorder: 'hover:border-slate-400',
    },
    {
      id: 'review',
      title: 'Claims Requiring Review',
      value: '38',
      subtitle: 'Pending auditor inspection',
      filterTarget: 'Missing Info',
      trend: 'SLA: 2.1 days remaining',
      trendPositive: false,
      icon: AlertCircle,
      accentBorder: 'hover:border-amber-400',
    },
    {
      id: 'violations',
      title: 'Policy Violations',
      value: '12',
      subtitle: 'Hard policy caps breached',
      filterTarget: 'Policy Violation',
      trend: '₹48,200 non-compliant volume',
      trendPositive: false,
      icon: ShieldAlert,
      accentBorder: 'hover:border-rose-400',
    },
    {
      id: 'duplicates',
      title: 'Duplicate Candidates',
      value: '5',
      subtitle: 'High perceptual hash match',
      filterTarget: 'Duplicate Candidate',
      trend: '₹8,940 potential dual billing',
      trendPositive: false,
      icon: Copy,
      accentBorder: 'hover:border-amber-400',
    },
    {
      id: 'unreadable',
      title: 'Unreadable Receipts',
      value: '7',
      subtitle: 'Thermal fade / missing GST',
      filterTarget: 'Unreadable Receipt',
      trend: 'Action requested from submitter',
      trendPositive: false,
      icon: FileX,
      accentBorder: 'hover:border-slate-400',
    },
  ];

  const categoryData = [
    { name: 'Travel', pct: 38, amount: '₹5,41,500', color: '#1E293B' },
    { name: 'Lodging', pct: 30, amount: '₹4,27,500', color: '#475569' },
    { name: 'Meals', pct: 18, amount: '₹2,56,500', color: '#94A3B8' },
    { name: 'Supplies', pct: 14, amount: '₹1,99,500', color: '#CBD5E1' },
  ];

  const handleKpiClick = (filterTarget: string) => {
    onFilterQueue(filterTarget);
    onNavigate('audit-queue');
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Top Banner / Triage Headline */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-lg border border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Autonomous Audit Pipeline
            </span>
            <span className="text-slate-300">·</span>
            <span className="text-xs text-slate-500">October 2026 Audit Run</span>
          </div>
          <h1 className="text-xl font-bold text-slate-900 mt-1">
            Enterprise Spend Compliance Overview
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            184 total OCR receipts scanned. 68% automatically verified clean under active policy ruleset.
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => onNavigate('audit-queue')}
            className="flex items-center gap-2 px-3.5 py-2 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded transition-colors whitespace-nowrap shadow-xs"
          >
            <span>Open AI Audit Queue</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* 6 Interactive KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {kpis.map((kpi) => {
          const Icon = kpi.icon;
          return (
            <div
              key={kpi.id}
              onClick={() => handleKpiClick(kpi.filterTarget)}
              className={`cursor-pointer bg-white p-4 rounded-lg border border-slate-200 transition-all hover:shadow-xs group ${kpi.accentBorder}`}
            >
              <div className="flex items-center justify-between text-slate-400 group-hover:text-slate-700 transition-colors">
                <span className="text-[11px] font-medium text-slate-600 truncate">
                  {kpi.title}
                </span>
                <Icon className="h-3.5 w-3.5 shrink-0" />
              </div>
              <div className="mt-2 text-xl font-bold font-mono text-slate-900 tracking-tight">
                {kpi.value}
              </div>
              <div className="mt-1 text-[11px] text-slate-500 truncate">
                {kpi.subtitle}
              </div>
              <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between text-[10px]">
                <span className="text-slate-500 font-mono">{kpi.trend}</span>
                <ChevronRight className="h-3 w-3 text-slate-300 group-hover:text-slate-600 group-hover:translate-x-0.5 transition-transform" />
              </div>
            </div>
          );
        })}
      </div>

      {/* 4 Visual Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Chart 1: Monthly Spend vs. Budget Trajectory */}
        <div className="bg-white p-5 rounded-lg border border-slate-200">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-slate-900">
                Monthly Spend vs. Budget Trajectory
              </h2>
              <p className="text-[11px] text-slate-500">
                FY27 Q2-Q3 Cumulative Departmental Outlays
              </p>
            </div>
            <div className="flex items-center gap-3 text-[11px] font-medium">
              <span className="flex items-center gap-1.5 text-slate-700">
                <span className="h-2 w-3 bg-slate-900 rounded-xs" /> Actual Spend
              </span>
              <span className="flex items-center gap-1.5 text-slate-400">
                <span className="h-0.5 w-3 bg-slate-300" /> Budget Cap (₹15L)
              </span>
            </div>
          </div>

          {/* SVG Area/Line Chart */}
          <div className="h-52 w-full pt-2">
            <svg viewBox="0 0 500 200" className="w-full h-full overflow-visible">
              {/* Grid Lines */}
              <line x1="40" y1="20" x2="480" y2="20" stroke="#F1F5F9" strokeWidth="1" />
              <line x1="40" y1="60" x2="480" y2="60" stroke="#F1F5F9" strokeWidth="1" />
              <line x1="40" y1="100" x2="480" y2="100" stroke="#F1F5F9" strokeWidth="1" />
              <line x1="40" y1="140" x2="480" y2="140" stroke="#F1F5F9" strokeWidth="1" />
              <line x1="40" y1="180" x2="480" y2="180" stroke="#E2E8F0" strokeWidth="1" />

              {/* Y Axis Labels */}
              <text x="32" y="24" textAnchor="end" fontSize="10" fill="#94A3B8" className="font-mono">₹16L</text>
              <text x="32" y="64" textAnchor="end" fontSize="10" fill="#94A3B8" className="font-mono">₹14L</text>
              <text x="32" y="104" textAnchor="end" fontSize="10" fill="#94A3B8" className="font-mono">₹12L</text>
              <text x="32" y="144" textAnchor="end" fontSize="10" fill="#94A3B8" className="font-mono">₹10L</text>
              <text x="32" y="184" textAnchor="end" fontSize="10" fill="#94A3B8" className="font-mono">₹0</text>

              {/* Budget Line (Dashed) */}
              <line x1="50" y1="45" x2="470" y2="45" stroke="#94A3B8" strokeWidth="1.5" strokeDasharray="4 4" />

              {/* Gradient Area */}
              <defs>
                <linearGradient id="spendGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#1E293B" stopOpacity="0.12" />
                  <stop offset="100%" stopColor="#1E293B" stopOpacity="0.0" />
                </linearGradient>
              </defs>

              {/* Points: May(11.2L->120), Jun(12.8L->88), Jul(13.4L->75), Aug(12.1L->102), Sep(14.8L->48), Oct(14.25L->58) */}
              <polygon
                points="70,180 70,120 150,88 230,75 310,102 390,48 470,58 470,180"
                fill="url(#spendGrad)"
              />
              <polyline
                points="70,120 150,88 230,75 310,102 390,48 470,58"
                fill="none"
                stroke="#1E293B"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />

              {/* Data points */}
              {[
                { x: 70, y: 120, label: 'May', val: '₹11.2L' },
                { x: 150, y: 88, label: 'Jun', val: '₹12.8L' },
                { x: 230, y: 75, label: 'Jul', val: '₹13.4L' },
                { x: 310, y: 102, label: 'Aug', val: '₹12.1L' },
                { x: 390, y: 48, label: 'Sep', val: '₹14.8L' },
                { x: 470, y: 58, label: 'Oct', val: '₹14.25L' },
              ].map((pt, i) => (
                <g key={i}>
                  <circle cx={pt.x} cy={pt.y} r="3.5" fill="#1E293B" stroke="#FFFFFF" strokeWidth="2" />
                  <text x={pt.x} y="196" textAnchor="middle" fontSize="10" fill="#64748B" className="font-mono">
                    {pt.label}
                  </text>
                </g>
              ))}
            </svg>
          </div>
        </div>

        {/* Chart 2: Expense Category Breakdown (Donut) */}
        <div className="bg-white p-5 rounded-lg border border-slate-200">
          <div className="flex items-center justify-between mb-2">
            <div>
              <h2 className="text-sm font-bold text-slate-900">
                Expense Category Breakdown
              </h2>
              <p className="text-[11px] text-slate-500">
                Volume share across major corporate accounts
              </p>
            </div>
            <span className="text-xs font-mono text-slate-500">₹14.25L total</span>
          </div>

          <div className="flex items-center justify-between pt-2">
            {/* SVG Donut */}
            <div className="relative flex items-center justify-center w-48 h-48 shrink-0">
              <svg viewBox="0 0 100 100" className="w-full h-full transform -rotate-90">
                {/* Travel: 38% -> strokeDasharray: 38 62, offset: 0 */}
                <circle
                  cx="50"
                  cy="50"
                  r="36"
                  fill="transparent"
                  stroke="#1E293B"
                  strokeWidth="14"
                  strokeDasharray="86 140"
                  strokeDashoffset="0"
                  className="transition-all hover:opacity-80 cursor-pointer"
                  onMouseEnter={() => setHoveredDonut('Travel')}
                  onMouseLeave={() => setHoveredDonut(null)}
                />
                {/* Lodging: 30% -> strokeDasharray: 68 158 */}
                <circle
                  cx="50"
                  cy="50"
                  r="36"
                  fill="transparent"
                  stroke="#475569"
                  strokeWidth="14"
                  strokeDasharray="68 158"
                  strokeDashoffset="-86"
                  className="transition-all hover:opacity-80 cursor-pointer"
                  onMouseEnter={() => setHoveredDonut('Lodging')}
                  onMouseLeave={() => setHoveredDonut(null)}
                />
                {/* Meals: 18% -> strokeDasharray: 41 185 */}
                <circle
                  cx="50"
                  cy="50"
                  r="36"
                  fill="transparent"
                  stroke="#94A3B8"
                  strokeWidth="14"
                  strokeDasharray="41 185"
                  strokeDashoffset="-154"
                  className="transition-all hover:opacity-80 cursor-pointer"
                  onMouseEnter={() => setHoveredDonut('Meals')}
                  onMouseLeave={() => setHoveredDonut(null)}
                />
                {/* Supplies: 14% -> strokeDasharray: 31 195 */}
                <circle
                  cx="50"
                  cy="50"
                  r="36"
                  fill="transparent"
                  stroke="#CBD5E1"
                  strokeWidth="14"
                  strokeDasharray="31 195"
                  strokeDashoffset="-195"
                  className="transition-all hover:opacity-80 cursor-pointer"
                  onMouseEnter={() => setHoveredDonut('Supplies')}
                  onMouseLeave={() => setHoveredDonut(null)}
                />
              </svg>

              {/* Center text */}
              <div className="absolute text-center pointer-events-none">
                <span className="text-[10px] uppercase font-semibold text-slate-400">
                  {hoveredDonut || 'Primary'}
                </span>
                <div className="text-base font-bold font-mono text-slate-900">
                  {hoveredDonut
                    ? categoryData.find((c) => c.name === hoveredDonut)?.pct + '%'
                    : '38% Travel'}
                </div>
              </div>
            </div>

            {/* Legend with Amounts */}
            <div className="flex-1 pl-6 space-y-2.5">
              {categoryData.map((cat) => (
                <div
                  key={cat.name}
                  onMouseEnter={() => setHoveredDonut(cat.name)}
                  onMouseLeave={() => setHoveredDonut(null)}
                  className={`flex items-center justify-between p-1.5 rounded transition-colors cursor-pointer ${
                    hoveredDonut === cat.name ? 'bg-slate-50' : ''
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="h-2.5 w-2.5 rounded-xs"
                      style={{ backgroundColor: cat.color }}
                    />
                    <span className="text-xs font-medium text-slate-700">
                      {cat.name}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-xs font-mono font-semibold text-slate-900">
                      {cat.amount}
                    </span>
                    <span className="text-[11px] text-slate-400 font-mono ml-2">
                      ({cat.pct}%)
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Chart 3: 3-Valued Audit Status Distribution */}
        <div className="bg-white p-5 rounded-lg border border-slate-200">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-sm font-bold text-slate-900">
                3-Valued Audit Status Distribution
              </h2>
              <p className="text-[11px] text-slate-500">
                Rigorous non-binary auditing: PASS / UNKNOWN (review) / FAIL
              </p>
            </div>
            <span className="text-[11px] text-slate-400 font-mono">184 receipts</span>
          </div>

          {/* Stacked Bar Container */}
          <div className="space-y-3 pt-2">
            <div className="h-6 w-full flex rounded overflow-hidden bg-slate-100">
              <div
                style={{ width: '68%' }}
                className="bg-emerald-600 hover:bg-emerald-700 transition-colors flex items-center justify-center text-[10px] font-mono text-white font-medium cursor-pointer"
                title="PASS: 68% (125 claims)"
                onClick={() => handleKpiClick('All')}
              >
                PASS 68%
              </div>
              <div
                style={{ width: '18%' }}
                className="bg-amber-500 hover:bg-amber-600 transition-colors flex items-center justify-center text-[10px] font-mono text-white font-medium cursor-pointer"
                title="UNKNOWN: 18% (33 claims)"
                onClick={() => handleKpiClick('Missing Info')}
              >
                UNKNOWN 18%
              </div>
              <div
                style={{ width: '14%' }}
                className="bg-rose-600 hover:bg-rose-700 transition-colors flex items-center justify-center text-[10px] font-mono text-white font-medium cursor-pointer"
                title="FAIL: 14% (26 claims)"
                onClick={() => handleKpiClick('Policy Violation')}
              >
                FAIL 14%
              </div>
            </div>

            {/* Legend & Breakdown Cards */}
            <div className="grid grid-cols-3 gap-2 pt-2">
              <div
                onClick={() => handleKpiClick('All')}
                className="cursor-pointer p-2.5 rounded border border-emerald-100 bg-emerald-50/40 hover:bg-emerald-50 transition-colors"
              >
                <div className="flex items-center gap-1.5 text-emerald-800 text-xs font-semibold">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>PASS</span>
                </div>
                <div className="mt-1 font-mono text-sm font-bold text-slate-900">
                  ₹9,68,000
                </div>
                <div className="text-[10px] text-slate-500 font-mono">
                  125 claims (68%)
                </div>
              </div>

              <div
                onClick={() => handleKpiClick('Missing Info')}
                className="cursor-pointer p-2.5 rounded border border-amber-100 bg-amber-50/40 hover:bg-amber-50 transition-colors"
              >
                <div className="flex items-center gap-1.5 text-amber-800 text-xs font-semibold">
                  <AlertCircle className="h-3.5 w-3.5" />
                  <span>UNKNOWN</span>
                </div>
                <div className="mt-1 font-mono text-sm font-bold text-slate-900">
                  ₹2,58,000
                </div>
                <div className="text-[10px] text-slate-500 font-mono">
                  33 claims (18%)
                </div>
              </div>

              <div
                onClick={() => handleKpiClick('Policy Violation')}
                className="cursor-pointer p-2.5 rounded border border-rose-100 bg-rose-50/40 hover:bg-rose-50 transition-colors"
              >
                <div className="flex items-center gap-1.5 text-rose-800 text-xs font-semibold">
                  <ShieldAlert className="h-3.5 w-3.5" />
                  <span>FAIL</span>
                </div>
                <div className="mt-1 font-mono text-sm font-bold text-slate-900">
                  ₹1,99,000
                </div>
                <div className="text-[10px] text-slate-500 font-mono">
                  26 claims (14%)
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Chart 4: Policy Violation Trends over Time */}
        <div className="bg-white p-5 rounded-lg border border-slate-200">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-slate-900">
                Policy Violation Trends by Week
              </h2>
              <p className="text-[11px] text-slate-500">
                Active infractions grouped by clause classification
              </p>
            </div>
            <span className="text-[11px] text-slate-500 font-mono">Last 5 Weeks</span>
          </div>

          <div className="h-44 flex items-end justify-between gap-4 pt-4 px-2">
            {[
              { week: 'W1 Sep', meal: 4, lodg: 2, item: 1, total: 7 },
              { week: 'W2 Sep', meal: 6, lodg: 1, item: 3, total: 10 },
              { week: 'W3 Sep', meal: 3, lodg: 2, item: 2, total: 7 },
              { week: 'W4 Sep', meal: 8, lodg: 3, item: 2, total: 13 },
              { week: 'W1 Oct', meal: 5, lodg: 1, item: 4, total: 10 },
              { week: 'W2 Oct', meal: 3, lodg: 1, item: 2, total: 6 },
            ].map((col, idx) => {
              const maxH = 14;
              const heightPct = (col.total / maxH) * 100;
              return (
                <div key={idx} className="flex-1 flex flex-col items-center gap-1.5 group">
                  <span className="text-[10px] font-mono text-slate-400 group-hover:text-slate-900 transition-colors">
                    {col.total}
                  </span>
                  <div className="w-full max-w-[32px] h-32 bg-slate-50 rounded-t flex flex-col justify-end overflow-hidden">
                    <div
                      style={{ height: `${(col.meal / maxH) * 100}%` }}
                      className="bg-slate-800 w-full"
                      title={`Meals: ${col.meal}`}
                    />
                    <div
                      style={{ height: `${(col.item / maxH) * 100}%` }}
                      className="bg-slate-500 w-full"
                      title={`Prohibited Items: ${col.item}`}
                    />
                    <div
                      style={{ height: `${(col.lodg / maxH) * 100}%` }}
                      className="bg-slate-300 w-full"
                      title={`Lodging: ${col.lodg}`}
                    />
                  </div>
                  <span className="text-[10px] text-slate-500 font-mono whitespace-nowrap">
                    {col.week}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Bar Chart Legend */}
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-center gap-4 text-[11px] text-slate-600">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-xs bg-slate-800" /> Meal Cap (POL-4.2)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-xs bg-slate-500" /> Prohibited (POL-6.1)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-xs bg-slate-300" /> Lodging (POL-5.1)
            </span>
          </div>
        </div>
      </div>

      {/* D3 Compliance Risk Heatmap Card */}
      <ComplianceHeatmap
        claims={claims}
        onFilterQueue={onFilterQueue}
        onNavigate={onNavigate}
      />

      {/* Priority Triage Quick Actions */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-200 bg-slate-50/60 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              Urgent Review Required · Top Audit Exceptions
            </h3>
          </div>
          <button
            onClick={() => onNavigate('audit-queue')}
            className="text-xs text-slate-600 hover:text-slate-900 font-medium flex items-center gap-1 transition-colors"
          >
            <span>View Full Queue ({claims.length})</span>
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="divide-y divide-slate-100">
          {claims
            .filter((c) => c.status !== 'PASS')
            .slice(0, 4)
            .map((claim) => (
              <div
                key={claim.id}
                onClick={() => {
                  onSelectClaim(claim.id);
                  onNavigate('workbench');
                }}
                className="p-4 hover:bg-slate-50 flex flex-col md:flex-row md:items-center justify-between gap-3 cursor-pointer transition-colors"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-slate-900">
                      {claim.id}
                    </span>
                    <span className="text-slate-300">·</span>
                    <span className="text-xs font-semibold text-slate-800">
                      {claim.employeeName}
                    </span>
                    <span className="text-[11px] text-slate-500">
                      ({claim.employeeDept} / {claim.costCenter})
                    </span>
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                        claim.status === 'FAIL'
                          ? 'bg-rose-50 text-rose-700'
                          : 'bg-amber-50 text-amber-700'
                      }`}
                    >
                      {claim.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 font-medium">
                    {claim.merchantName} · <span className="font-mono">₹{claim.claimedAmount.toLocaleString('en-IN')}</span>
                  </p>
                  <p className="text-[11px] text-slate-500">
                    {claim.issueDescription}
                  </p>
                </div>

                <div className="flex items-center gap-3 shrink-0 self-end md:self-center">
                  <span className="text-[11px] font-mono text-slate-400">
                    Waiting {claim.daysWaiting}d
                  </span>
                  <button className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-slate-800 bg-white border border-slate-200 rounded hover:bg-slate-50 shadow-2xs transition-colors">
                    <span>Inspect in Workbench</span>
                    <ChevronRight className="h-3 w-3" />
                  </button>
                </div>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
};
