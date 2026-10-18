import React, { useState } from 'react';
import {
  Users,
  Store,
  CreditCard,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ShieldCheck,
  Search,
  ChevronRight,
  TrendingUp,
} from 'lucide-react';
import { EmployeeProfile, MerchantInsight, Claim, ActiveTab } from '../types';

interface EmployeeMerchantProfilesProps {
  employees: EmployeeProfile[];
  merchants: MerchantInsight[];
  claims: Claim[];
  onSelectClaim: (claimId: string) => void;
  onNavigate: (tab: ActiveTab) => void;
}

export const EmployeeMerchantProfiles: React.FC<EmployeeMerchantProfilesProps> = ({
  employees,
  merchants,
  claims,
  onSelectClaim,
  onNavigate,
}) => {
  const [activeSubTab, setActiveSubTab] = useState<'employees' | 'merchants'>('employees');
  const [selectedEmpId, setSelectedEmpId] = useState<string>(employees[0]?.id || 'EMP-1048');
  const [merchantSearch, setMerchantSearch] = useState('');

  const currentEmp = employees.find((e) => e.id === selectedEmpId) || employees[0];

  // Specific employee's claims
  const employeeClaims = claims.filter((c) => c.employeeId === currentEmp.id);

  // Timeliness calculations
  const totalSubmissions = currentEmp.totalClaimsCount;
  const onTimePct = Math.round((currentEmp.onTimeSubmissionsCount / totalSubmissions) * 100);
  const delayedPct = Math.round((currentEmp.delayedSubmissionsCount / totalSubmissions) * 100);
  const overduePct = 100 - onTimePct - delayedPct;

  const filteredMerchants = merchants.filter((m) =>
    m.name.toLowerCase().includes(merchantSearch.toLowerCase()) ||
    m.category.toLowerCase().includes(merchantSearch.toLowerCase())
  );

  return (
    <div className="space-y-6 pb-12">
      {/* View Header with Sub-tab Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-lg border border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <Users className="h-4 w-4 text-slate-700" />
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Employee Profiles & Merchant Insights
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Holistic compliance health tracking, submission timeliness SLAs, and vendor risk profiles.
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-lg text-xs font-medium">
          <button
            onClick={() => setActiveSubTab('employees')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded transition-colors ${
              activeSubTab === 'employees'
                ? 'bg-white text-slate-900 shadow-xs font-semibold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Users className="h-3.5 w-3.5" />
            <span>Employee Detail View</span>
          </button>
          <button
            onClick={() => setActiveSubTab('merchants')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded transition-colors ${
              activeSubTab === 'merchants'
                ? 'bg-white text-slate-900 shadow-xs font-semibold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Store className="h-3.5 w-3.5" />
            <span>Merchant Intelligence</span>
          </button>
        </div>
      </div>

      {activeSubTab === 'employees' ? (
        <div className="space-y-5">
          {/* Employee Selector Bar */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 bg-white p-3 rounded-lg border border-slate-200">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider shrink-0 mr-2">
              Lookup Employee:
            </span>
            {employees.map((emp) => (
              <button
                key={emp.id}
                onClick={() => setSelectedEmpId(emp.id)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded border text-xs transition-colors whitespace-nowrap ${
                  selectedEmpId === emp.id
                    ? 'border-slate-900 bg-slate-900 text-white font-medium shadow-xs'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                }`}
              >
                <span className="font-mono">{emp.id}</span>
                <span className="font-semibold">{emp.name}</span>
                <span
                  className={`text-[10px] font-mono px-1 rounded ${
                    selectedEmpId === emp.id ? 'bg-slate-800 text-slate-200' : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  Score: {emp.complianceHealthScore}%
                </span>
              </button>
            ))}
          </div>

          {/* Selected Employee Card Header */}
          <div className="bg-white p-5 rounded-lg border border-slate-200 shadow-2xs">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-100">
              <div className="flex items-center gap-3">
                <div className="h-12 w-12 rounded-full bg-slate-900 text-white flex items-center justify-center font-bold text-base">
                  {currentEmp.name.split(' ').map((n) => n[0]).join('')}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold text-slate-900">
                      {currentEmp.name}
                    </h2>
                    <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-800">
                      {currentEmp.id}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {currentEmp.role} · {currentEmp.department} · Manager: <strong className="text-slate-700">{currentEmp.manager}</strong>
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <div className="text-right">
                  <span className="text-[10px] uppercase font-semibold text-slate-400">
                    Corporate Card Status
                  </span>
                  <div className="flex items-center justify-end gap-1.5 text-xs font-semibold text-slate-800 mt-0.5">
                    <CreditCard className="h-3.5 w-3.5 text-slate-500" />
                    <span>{currentEmp.corporateCardAssigned ? 'AMEX Corporate Assigned' : 'Personal Reimbursable'}</span>
                  </div>
                </div>

                <div className="text-right pl-4 border-l border-slate-200">
                  <span className="text-[10px] uppercase font-semibold text-slate-400">
                    Compliance Health
                  </span>
                  <div className={`text-lg font-bold font-mono ${
                    currentEmp.complianceHealthScore >= 90
                      ? 'text-emerald-700'
                      : currentEmp.complianceHealthScore >= 80
                      ? 'text-amber-700'
                      : 'text-rose-700'
                  }`}>
                    {currentEmp.complianceHealthScore}% / 100
                  </div>
                </div>
              </div>
            </div>

            {/* 3 Visual Diagrams: Monthly Spend, Category Split, and Submission Timeliness Gauge */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5 pt-5">
              {/* Diagram 1: Individual Monthly Spend Bar Chart */}
              <div className="p-4 bg-slate-50 rounded border border-slate-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-slate-800">Monthly Expense Trend</span>
                  <span className="text-[10px] font-mono text-slate-400">Last 5 Months</span>
                </div>
                <div className="h-28 flex items-end justify-between gap-2 pt-2">
                  {currentEmp.monthlySpendHistory.map((m, idx) => {
                    const maxH = 80000;
                    const hPct = (m.amount / maxH) * 100;
                    return (
                      <div key={idx} className="flex-1 flex flex-col items-center gap-1">
                        <span className="text-[9px] font-mono text-slate-500">
                          ₹{(m.amount / 1000).toFixed(0)}k
                        </span>
                        <div className="w-full bg-slate-200 rounded-t h-20 flex items-end">
                          <div
                            style={{ height: `${hPct}%` }}
                            className="w-full bg-slate-900 rounded-t hover:bg-slate-700 transition-colors"
                            title={`${m.month}: ₹${m.amount.toLocaleString('en-IN')}`}
                          />
                        </div>
                        <span className="text-[10px] font-mono text-slate-600">{m.month}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Diagram 2: Category Split Ring Chart */}
              <div className="p-4 bg-slate-50 rounded border border-slate-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-slate-800">Category Spend Split</span>
                  <span className="text-[10px] font-mono text-slate-400">Total Billed</span>
                </div>
                <div className="space-y-1.5 pt-1">
                  {currentEmp.categoryDistribution.map((cat) => {
                    const totalEmpSpend = currentEmp.categoryDistribution.reduce((a, b) => a + b.amount, 0) || 1;
                    const pct = Math.round((cat.amount / totalEmpSpend) * 100);
                    return (
                      <div key={cat.category} className="text-xs space-y-0.5">
                        <div className="flex justify-between text-[11px]">
                          <span className="text-slate-700 truncate">{cat.category}</span>
                          <span className="font-mono font-medium text-slate-900">
                            ₹{cat.amount.toLocaleString('en-IN')} ({pct}%)
                          </span>
                        </div>
                        <div className="h-1.5 w-full bg-slate-200 rounded-full overflow-hidden">
                          <div
                            style={{ width: `${pct}%` }}
                            className="h-full bg-slate-800 rounded-full"
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Diagram 3: Receipt Submission Timeliness Gauge */}
              <div className="p-4 bg-slate-50 rounded border border-slate-200 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold text-slate-800">
                      Receipt Submission Timeliness Gauge
                    </span>
                    <Clock className="h-3.5 w-3.5 text-slate-400" />
                  </div>
                  <p className="text-[10px] text-slate-500">
                    SLA Compliance (7 Calendar Days window from receipt date)
                  </p>
                </div>

                {/* Progress Bar Gauge */}
                <div className="space-y-2 py-2">
                  <div className="h-4 w-full flex rounded overflow-hidden bg-slate-200">
                    <div
                      style={{ width: `${onTimePct}%` }}
                      className="bg-emerald-600 text-white font-mono text-[9px] flex items-center justify-center font-bold"
                      title={`On-time: ${onTimePct}%`}
                    >
                      {onTimePct}%
                    </div>
                    <div
                      style={{ width: `${delayedPct}%` }}
                      className="bg-amber-500 text-white font-mono text-[9px] flex items-center justify-center font-bold"
                      title={`Delayed (8-14d): ${delayedPct}%`}
                    >
                      {delayedPct}%
                    </div>
                    {overduePct > 0 && (
                      <div
                        style={{ width: `${overduePct}%` }}
                        className="bg-rose-600 text-white font-mono text-[9px] flex items-center justify-center font-bold"
                        title={`Overdue (>14d): ${overduePct}%`}
                      >
                        {overduePct}%
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-3 gap-1 text-[10px] text-center font-mono pt-1">
                    <div className="text-emerald-800 bg-emerald-50 py-1 rounded">
                      <div>On-Time (&le;7d)</div>
                      <div className="font-bold">{currentEmp.onTimeSubmissionsCount} claims</div>
                    </div>
                    <div className="text-amber-800 bg-amber-50 py-1 rounded">
                      <div>Delayed (8-14d)</div>
                      <div className="font-bold">{currentEmp.delayedSubmissionsCount} claims</div>
                    </div>
                    <div className="text-rose-800 bg-rose-50 py-1 rounded">
                      <div>Overdue (&gt;14d)</div>
                      <div className="font-bold">{currentEmp.overdueSubmissionsCount} claims</div>
                    </div>
                  </div>
                </div>

                <div className="text-[10px] text-slate-500 text-center">
                  Target SLA: 90% submissions within 7 days
                </div>
              </div>
            </div>
          </div>

          {/* Employee Past Record Ledger */}
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden shadow-2xs">
            <div className="p-4 border-b border-slate-200 bg-slate-50/70 flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Employee Historical Expense Claims ({employeeClaims.length})
              </h3>
              <span className="text-[11px] text-slate-400">
                Verified submission latencies & exceptions
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/30 text-slate-400 uppercase text-[10px] font-semibold">
                    <th className="py-2.5 px-4">Claim ID</th>
                    <th className="py-2.5 px-4">Merchant</th>
                    <th className="py-2.5 px-4">Category</th>
                    <th className="py-2.5 px-4 text-right">Amount (INR)</th>
                    <th className="py-2.5 px-4">Expense Date</th>
                    <th className="py-2.5 px-4">Submission Latency</th>
                    <th className="py-2.5 px-4 text-center">Audit Status</th>
                    <th className="py-2.5 px-4">Approval Stage</th>
                    <th className="py-2.5 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {employeeClaims.map((claim) => (
                    <tr key={claim.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="py-3 px-4 font-mono font-semibold text-slate-900">
                        {claim.id}
                      </td>
                      <td className="py-3 px-4 text-slate-800 font-medium">
                        {claim.merchantName}
                      </td>
                      <td className="py-3 px-4 text-slate-600">
                        {claim.category}
                      </td>
                      <td className="py-3 px-4 text-right font-mono font-bold text-slate-900">
                        ₹{claim.claimedAmount.toLocaleString('en-IN')}
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-500">
                        {claim.expenseDate}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`font-mono text-[11px] font-medium px-2 py-0.5 rounded ${
                            claim.submissionLatencyDays > 7
                              ? 'bg-rose-50 text-rose-700'
                              : 'bg-emerald-50 text-emerald-700'
                          }`}
                        >
                          {claim.submissionLatencyDays === 0
                            ? 'Same day'
                            : `Uploaded in ${claim.submissionLatencyDays} days`}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span
                          className={`inline-block text-[10px] font-semibold px-2 py-0.5 rounded ${
                            claim.status === 'PASS'
                              ? 'bg-emerald-50 text-emerald-700'
                              : claim.status === 'FAIL'
                              ? 'bg-rose-50 text-rose-700'
                              : 'bg-amber-50 text-amber-700'
                          }`}
                        >
                          {claim.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-700">
                        {claim.approvalStage}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => {
                            onSelectClaim(claim.id);
                            onNavigate('workbench');
                          }}
                          className="px-2.5 py-1 text-[11px] font-medium text-slate-700 bg-white border border-slate-200 rounded hover:bg-slate-50"
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        /* Tab 2: Merchant Insights Tab */
        <div className="space-y-4">
          <div className="flex items-center justify-between bg-white p-3 rounded-lg border border-slate-200">
            <div className="relative w-80">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                value={merchantSearch}
                onChange={(e) => setMerchantSearch(e.target.value)}
                placeholder="Search vendor name, category..."
                className="w-full h-8 pl-8.5 pr-3 text-xs bg-slate-50 border border-slate-200 rounded text-slate-800 focus:outline-none focus:border-slate-400 focus:bg-white"
              />
            </div>
            <span className="text-xs font-mono text-slate-500">
              {filteredMerchants.length} corporate vendors tracked
            </span>
          </div>

          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden shadow-2xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-400 uppercase text-[10px] font-semibold">
                    <th className="py-2.5 px-4">Merchant Name</th>
                    <th className="py-2.5 px-4">Category</th>
                    <th className="py-2.5 px-4 text-right">Total Volume (INR)</th>
                    <th className="py-2.5 px-4 text-center">Claim Count</th>
                    <th className="py-2.5 px-4 text-center">Error / Exception Rate</th>
                    <th className="py-2.5 px-4 text-center">Missing Tax Rate</th>
                    <th className="py-2.5 px-4 text-center">Risk Level</th>
                    <th className="py-2.5 px-4">Audit Recurring Pattern</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredMerchants.map((m) => (
                    <tr key={m.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="py-3 px-4 font-semibold text-slate-900">
                        {m.name}
                      </td>
                      <td className="py-3 px-4 text-slate-600">
                        {m.category}
                      </td>
                      <td className="py-3 px-4 text-right font-mono font-bold text-slate-900">
                        ₹{m.totalVolume.toLocaleString('en-IN')}
                      </td>
                      <td className="py-3 px-4 text-center font-mono text-slate-700">
                        {m.claimCount}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span
                          className={`font-mono text-xs font-semibold px-2 py-0.5 rounded ${
                            m.errorRate > 20
                              ? 'bg-rose-50 text-rose-700'
                              : m.errorRate > 10
                              ? 'bg-amber-50 text-amber-700'
                              : 'bg-emerald-50 text-emerald-700'
                          }`}
                        >
                          {m.errorRate}%
                        </span>
                      </td>
                      <td className="py-3 px-4 text-center font-mono text-slate-600">
                        {m.missingTaxRate}%
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span
                          className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${
                            m.riskLevel === 'HIGH'
                              ? 'bg-rose-100 text-rose-800'
                              : m.riskLevel === 'MEDIUM'
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {m.riskLevel}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-600 max-w-xs text-[11px]">
                        {m.commonIssue}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
