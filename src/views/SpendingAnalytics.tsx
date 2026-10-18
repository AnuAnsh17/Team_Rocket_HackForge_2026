import React, { useState } from 'react';
import {
  BarChart3,
  TrendingUp,
  AlertTriangle,
  Building2,
  MapPin,
  Filter,
  DollarSign,
  ArrowUpRight,
  ShieldAlert,
} from 'lucide-react';
import { EmployeeProfile, Claim, ActiveTab } from '../types';

interface SpendingAnalyticsProps {
  claims: Claim[];
  employees: EmployeeProfile[];
  onSelectClaim: (claimId: string) => void;
  onNavigate: (tab: ActiveTab) => void;
}

export const SpendingAnalytics: React.FC<SpendingAnalyticsProps> = ({
  claims,
  employees,
  onSelectClaim,
  onNavigate,
}) => {
  const [activeDimension, setActiveDimension] = useState<'dept' | 'tier' | 'category'>('dept');
  const [ledgerThreshold, setLedgerThreshold] = useState<'all' | 'approaching' | 'exceeded'>('all');

  const deptData = [
    { name: 'Engineering', spend: 615000, budget: 650000, color: '#1E293B' },
    { name: 'Sales', spend: 420000, budget: 450000, color: '#475569' },
    { name: 'Marketing', spend: 210000, budget: 200000, color: '#DC2626' }, // Over budget
    { name: 'Operations', spend: 180000, budget: 200000, color: '#94A3B8' },
  ];

  const cityTierData = [
    { tier: 'Tier 1 Metro (BLR, BOM, DEL)', spend: 985000, pct: 69, claims: 122 },
    { tier: 'Tier 2 Emerging (PUN, HYD, JAI)', spend: 320000, pct: 22, claims: 45 },
    { tier: 'Tier 3 / Regional Towns', spend: 120000, pct: 9, claims: 17 },
  ];

  // Cumulative Ledger items
  const ledgerItems = [
    {
      employee: 'Arjun Das',
      empId: 'EMP-1184',
      costCenter: 'CC-202 (Growth)',
      category: 'Supplies',
      monthlyCap: 15000,
      spent: 16800,
      status: 'exceeded',
      excessAmount: 1800,
      lastClaimId: 'CLM-8495',
    },
    {
      employee: 'Rahul Sharma',
      empId: 'EMP-1048',
      costCenter: 'CC-402 (Platform)',
      category: 'Meals',
      monthlyCap: 10000,
      spent: 9060,
      status: 'approaching',
      excessAmount: 0,
      lastClaimId: 'CLM-8491',
    },
    {
      employee: 'Priya Nair',
      empId: 'EMP-1092',
      costCenter: 'CC-108 (Sales)',
      category: 'Client Dining',
      monthlyCap: 30000,
      spent: 26400,
      status: 'approaching',
      excessAmount: 0,
      lastClaimId: 'CLM-8496',
    },
    {
      employee: 'Sneha Kulkarni',
      empId: 'EMP-1055',
      costCenter: 'CC-401 (Exec)',
      category: 'Air Travel',
      monthlyCap: 60000,
      spent: 42800,
      status: 'normal',
      excessAmount: 0,
      lastClaimId: 'CLM-8497',
    },
    {
      employee: 'Vikram Patel',
      empId: 'EMP-1120',
      costCenter: 'CC-304 (Supply Chain)',
      category: 'Lodging',
      monthlyCap: 25000,
      spent: 12800,
      status: 'normal',
      excessAmount: 0,
      lastClaimId: 'CLM-8501',
    },
  ];

  const filteredLedger = ledgerItems.filter((item) => {
    if (ledgerThreshold === 'approaching') return item.status === 'approaching';
    if (ledgerThreshold === 'exceeded') return item.status === 'exceeded';
    return true;
  });

  return (
    <div className="space-y-6 pb-12">
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-lg border border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-slate-700" />
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Spending & Budget Analytics
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Multi-dimensional spend analysis across departments, city tiers, and cumulative thresholds.
          </p>
        </div>

        <div className="flex items-center gap-1.5 p-1 bg-slate-100 rounded-md text-xs font-medium">
          <button
            onClick={() => setActiveDimension('dept')}
            className={`px-3 py-1 rounded transition-colors ${
              activeDimension === 'dept'
                ? 'bg-white text-slate-900 shadow-xs font-semibold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            By Department
          </button>
          <button
            onClick={() => setActiveDimension('tier')}
            className={`px-3 py-1 rounded transition-colors ${
              activeDimension === 'tier'
                ? 'bg-white text-slate-900 shadow-xs font-semibold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            By City Tier
          </button>
        </div>
      </div>

      {/* Main Dimension Visualization */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Department Budget Allocation vs Spend */}
        <div className="bg-white p-5 rounded-lg border border-slate-200 space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
            <div>
              <h2 className="text-sm font-bold text-slate-900">
                Departmental Budget Utilization
              </h2>
              <p className="text-[11px] text-slate-500">
                Actual expenditure vs. authorized departmental allocation
              </p>
            </div>
            <span className="text-xs font-mono text-slate-500">Total: ₹14.25L</span>
          </div>

          <div className="space-y-4 pt-1">
            {deptData.map((d) => {
              const pct = (d.spend / d.budget) * 100;
              const isOver = pct > 100;
              return (
                <div key={d.name} className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-slate-800">{d.name}</span>
                    <div className="font-mono text-right">
                      <span className="font-bold text-slate-900">
                        ₹{d.spend.toLocaleString('en-IN')}
                      </span>{' '}
                      <span className="text-slate-400">/ ₹{d.budget.toLocaleString('en-IN')}</span>
                      <span className={`ml-2 font-semibold ${isOver ? 'text-rose-600' : 'text-slate-600'}`}>
                        ({pct.toFixed(0)}%)
                      </span>
                    </div>
                  </div>

                  <div className="h-2.5 w-full bg-slate-100 rounded-full overflow-hidden">
                    <div
                      style={{ width: `${Math.min(pct, 100)}%` }}
                      className={`h-full rounded-full transition-all ${
                        isOver ? 'bg-rose-600' : 'bg-slate-800'
                      }`}
                    />
                  </div>
                  {isOver && (
                    <div className="text-[10px] text-rose-600 flex items-center gap-1 font-medium">
                      <AlertTriangle className="h-3 w-3" />
                      <span>Exceeded monthly authorized budget cap by ₹{(d.spend - d.budget).toLocaleString('en-IN')}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* City Tier Expenditure Split */}
        <div className="bg-white p-5 rounded-lg border border-slate-200 space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
            <div>
              <h2 className="text-sm font-bold text-slate-900">
                City Tier Spend & Per-Diem Weight
              </h2>
              <p className="text-[11px] text-slate-500">
                Distribution across metro and regional hubs
              </p>
            </div>
            <MapPin className="h-4 w-4 text-slate-400" />
          </div>

          <div className="space-y-4 pt-1">
            {cityTierData.map((tier) => (
              <div key={tier.tier} className="p-3 bg-slate-50 rounded border border-slate-200 space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-800">{tier.tier}</span>
                  <span className="font-mono font-bold text-slate-900">
                    ₹{tier.spend.toLocaleString('en-IN')} ({tier.pct}%)
                  </span>
                </div>

                <div className="h-2 w-full bg-slate-200 rounded-full overflow-hidden">
                  <div
                    style={{ width: `${tier.pct}%` }}
                    className="h-full bg-slate-900 rounded-full"
                  />
                </div>

                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>{tier.claims} verified claims</span>
                  <span>Avg per claim: ₹{Math.round(tier.spend / tier.claims).toLocaleString('en-IN')}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Rolling Cumulative Expense Ledger */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden shadow-2xs">
        <div className="p-4 border-b border-slate-200 bg-slate-50/70 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              Rolling Cumulative Expense Ledger
            </h2>
            <p className="text-xs text-slate-500">
              Active tracking of individual employee and category caps approaching or exceeding limits.
            </p>
          </div>

          {/* Threshold Filter */}
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-[11px] text-slate-400 font-medium">Threshold:</span>
            <button
              onClick={() => setLedgerThreshold('all')}
              className={`px-2.5 py-1 rounded transition-colors ${
                ledgerThreshold === 'all'
                  ? 'bg-slate-900 text-white font-semibold'
                  : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
              }`}
            >
              All Ledgers
            </button>
            <button
              onClick={() => setLedgerThreshold('approaching')}
              className={`px-2.5 py-1 rounded transition-colors ${
                ledgerThreshold === 'approaching'
                  ? 'bg-amber-600 text-white font-semibold'
                  : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
              }`}
            >
              &gt; 80% Approaching
            </button>
            <button
              onClick={() => setLedgerThreshold('exceeded')}
              className={`px-2.5 py-1 rounded transition-colors ${
                ledgerThreshold === 'exceeded'
                  ? 'bg-rose-600 text-white font-semibold'
                  : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
              }`}
            >
              &gt; 100% Exceeded
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/30 text-slate-400 uppercase text-[10px] font-semibold">
                <th className="py-2.5 px-4">Employee</th>
                <th className="py-2.5 px-4">Cost Center</th>
                <th className="py-2.5 px-4">Category</th>
                <th className="py-2.5 px-4 text-right">Spent vs Cap</th>
                <th className="py-2.5 px-4">Utilization</th>
                <th className="py-2.5 px-4 text-center">Status</th>
                <th className="py-2.5 px-4 text-right">Recent Claim</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredLedger.map((row, idx) => {
                const utilPct = (row.spent / row.monthlyCap) * 100;
                return (
                  <tr key={idx} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-900">{row.employee}</div>
                      <div className="text-[11px] text-slate-400 font-mono">{row.empId}</div>
                    </td>
                    <td className="py-3 px-4 text-slate-600">
                      {row.costCenter}
                    </td>
                    <td className="py-3 px-4 font-medium text-slate-800">
                      {row.category}
                    </td>
                    <td className="py-3 px-4 text-right font-mono">
                      <span className="font-bold text-slate-900">
                        ₹{row.spent.toLocaleString('en-IN')}
                      </span>{' '}
                      <span className="text-slate-400">/ ₹{row.monthlyCap.toLocaleString('en-IN')}</span>
                    </td>
                    <td className="py-3 px-4 w-44">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                          <div
                            style={{ width: `${Math.min(utilPct, 100)}%` }}
                            className={`h-full ${
                              row.status === 'exceeded'
                                ? 'bg-rose-600'
                                : row.status === 'approaching'
                                ? 'bg-amber-500'
                                : 'bg-emerald-600'
                            }`}
                          />
                        </div>
                        <span className="text-[10px] font-mono text-slate-500 w-8 text-right">
                          {utilPct.toFixed(0)}%
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span
                        className={`inline-block text-[10px] font-semibold px-2 py-0.5 rounded ${
                          row.status === 'exceeded'
                            ? 'bg-rose-50 text-rose-700 border border-rose-200'
                            : row.status === 'approaching'
                            ? 'bg-amber-50 text-amber-700 border border-amber-200'
                            : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        }`}
                      >
                        {row.status.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => {
                          onSelectClaim(row.lastClaimId);
                          onNavigate('workbench');
                        }}
                        className="px-2.5 py-1 text-[11px] font-medium font-mono text-slate-700 bg-white border border-slate-200 rounded hover:bg-slate-100 transition-colors"
                      >
                        {row.lastClaimId}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
