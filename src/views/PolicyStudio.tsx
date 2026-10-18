import React, { useState } from 'react';
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  Edit2,
  Plus,
  History,
  ShieldCheck,
  Sparkles,
  BookOpen,
  ArrowRight,
  Check,
  X,
} from 'lucide-react';
import { PolicyRule } from '../types';

interface PolicyStudioProps {
  policyRules: PolicyRule[];
  onUpdateRule: (updatedRule: PolicyRule) => void;
  onAddRule: (newRule: PolicyRule) => void;
}

export const PolicyStudio: React.FC<PolicyStudioProps> = ({
  policyRules,
  onUpdateRule,
  onAddRule,
}) => {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [editingRule, setEditingRule] = useState<PolicyRule | null>(null);
  const [activeVersion, setActiveVersion] = useState('v2026.4 (Active)');

  const policyVersions = [
    {
      version: 'v2026.4 (Active)',
      effectiveDate: '2026-10-01',
      publishedBy: 'Preeti S. · Finance Committee',
      rulesCount: 7,
      status: 'Active',
      changelog: 'Added Tier 1 metro meal allowance update (₹1,000) and GSTIN validation check.',
    },
    {
      version: 'v2026.3',
      effectiveDate: '2026-06-01',
      publishedBy: 'A. Roy · VP Finance',
      rulesCount: 6,
      status: 'Archived',
      changelog: 'Introduced 7-day receipt submission SLA.',
    },
    {
      version: 'v2025.2',
      effectiveDate: '2025-11-15',
      publishedBy: 'Corporate Audit',
      rulesCount: 5,
      status: 'Archived',
      changelog: 'Initial baseline travel & entertainment ceilings.',
    },
  ];

  const handleSimulateUpload = () => {
    setIsUploading(true);
    setTimeout(() => {
      setIsUploading(false);
      setUploadSuccess(true);
      setTimeout(() => setUploadSuccess(false), 4000);
    }, 1200);
  };

  const handleSaveRule = () => {
    if (editingRule) {
      onUpdateRule(editingRule);
      setEditingRule(null);
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-lg border border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-slate-700" />
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Policy Studio & Rule Compiler
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            AI-assisted policy ingestion, clause-to-rule compilation, and historical version governance.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Active Environment:</span>
          <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200">
            {activeVersion}
          </span>
        </div>
      </div>

      {/* Top Upload Zone: Drag-and-drop Corporate Policy PDF */}
      <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-2xs">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-sm font-bold text-slate-900">
              Ingest Policy Document (PDF / DOCX)
            </h2>
            <p className="text-xs text-slate-500">
              Upload natural-language corporate policies; AI extracts category caps, tier rules, and exceptions.
            </p>
          </div>
          <span className="text-[11px] font-mono text-slate-400">
            Max 25MB · Semantic Parser Ready
          </span>
        </div>

        <div
          onClick={handleSimulateUpload}
          className={`cursor-pointer border-2 border-dashed rounded-lg p-6 text-center transition-all ${
            isUploading
              ? 'border-blue-400 bg-blue-50/40'
              : uploadSuccess
              ? 'border-emerald-400 bg-emerald-50/40'
              : 'border-slate-300 hover:border-slate-400 bg-slate-50/50 hover:bg-slate-50'
          }`}
        >
          <div className="flex flex-col items-center justify-center space-y-2">
            {isUploading ? (
              <div className="flex flex-col items-center space-y-2">
                <div className="h-7 w-7 border-2 border-slate-900 border-t-transparent rounded-full animate-spin" />
                <span className="text-xs font-semibold text-slate-800">
                  Parsing corporate clauses & extracting mathematical limits...
                </span>
              </div>
            ) : uploadSuccess ? (
              <div className="flex flex-col items-center space-y-1 text-emerald-700">
                <CheckCircle2 className="h-7 w-7" />
                <span className="text-xs font-bold">
                  Successfully Ingested "Global_Travel_Expense_Policy_2026.pdf"
                </span>
                <span className="text-[11px] text-slate-500">
                  7 verified clauses compiled into active ruleset.
                </span>
              </div>
            ) : (
              <>
                <UploadCloud className="h-8 w-8 text-slate-400" />
                <div className="text-xs text-slate-700 font-medium">
                  <span className="font-semibold text-slate-900 underline">
                    Click to upload
                  </span>{' '}
                  or drag and drop corporate policy manual
                </div>
                <div className="text-[11px] text-slate-400">
                  Example: <em>Global_Travel_Expense_Policy_2026.pdf</em> (Click to simulate ingestion)
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Rule Verification Grid: Editable Cards */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-slate-900">
              Active Rule Logic & Clause Citations ({policyRules.length})
            </h2>
            <p className="text-xs text-slate-500">
              Mathematical rules compiled from human corporate policy text.
            </p>
          </div>
          <button
            onClick={() => {
              const newRule: PolicyRule = {
                id: `pol-${Date.now()}`,
                code: `POL-${(policyRules.length + 1).toFixed(1)}`,
                title: 'New Custom Spending Limit',
                category: 'Supplies',
                description: 'Custom expense limit compiled from policy clause.',
                ruleLogic: 'amount <= 5000 INR',
                clauseCitation: 'Section 9, Clause 9.1',
                limitAmount: 5000,
                currency: 'INR',
                period: 'Per-Claim',
                cityTier: 'All',
                status: 'Active',
                lastUpdated: '2026-10-17',
              };
              onAddRule(newRule);
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-800 bg-white border border-slate-200 rounded hover:bg-slate-50 shadow-2xs transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Add Rule</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {policyRules.map((rule) => (
            <div
              key={rule.id}
              className="bg-white rounded-lg border border-slate-200 p-4 space-y-3 shadow-2xs flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-xs font-bold text-slate-900">
                      {rule.code}
                    </span>
                    <span className="text-[10px] text-slate-400">·</span>
                    <span className="text-[11px] font-medium text-slate-600">
                      {rule.category}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono px-1.5 py-0.2 bg-emerald-50 text-emerald-700 rounded font-semibold">
                    {rule.status}
                  </span>
                </div>

                <div className="mt-2.5">
                  <h3 className="text-xs font-bold text-slate-900 leading-snug">
                    {rule.title}
                  </h3>
                  <p className="text-[11px] text-slate-500 mt-1 line-clamp-2">
                    {rule.description}
                  </p>
                </div>

                {/* Rule Logic Formula */}
                <div className="mt-3 p-2 bg-slate-50 rounded border border-slate-200 font-mono text-[11px] text-slate-800">
                  <span className="text-[9px] uppercase font-bold text-slate-400 block mb-0.5">
                    Rule Logic:
                  </span>
                  <code className="text-slate-900 font-semibold">{rule.ruleLogic}</code>
                </div>

                {/* Source Citation */}
                <div className="mt-2 flex items-center justify-between text-[11px]">
                  <span className="text-slate-400">Source:</span>
                  <span className="font-mono text-slate-700 font-medium">
                    {rule.clauseCitation}
                  </span>
                </div>
              </div>

              {/* Card Action Buttons */}
              <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
                <span className="text-[10px] text-slate-400 font-mono">
                  Updated: {rule.lastUpdated}
                </span>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setEditingRule(rule)}
                    className="p-1 text-slate-500 hover:text-slate-800 rounded hover:bg-slate-100 transition-colors"
                    title="Edit Rule Parameters"
                  >
                    <Edit2 className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => {
                      onUpdateRule({
                        ...rule,
                        status: 'Active',
                        lastUpdated: new Date().toISOString().split('T')[0],
                      });
                    }}
                    className="flex items-center gap-1 px-2 py-1 text-[11px] font-semibold text-emerald-800 bg-emerald-50 hover:bg-emerald-100 rounded transition-colors"
                  >
                    <Check className="h-3 w-3" />
                    <span>Confirm</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Policy Version History Table */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden shadow-2xs">
        <div className="p-4 border-b border-slate-200 bg-slate-50/70 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <History className="h-4 w-4 text-slate-600" />
            <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              Policy Version History & Historical Evaluation
            </h2>
          </div>
          <span className="text-[11px] text-slate-500">
            Immutable version audit record
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 text-slate-400 uppercase text-[10px] font-semibold bg-slate-50/30">
                <th className="py-2.5 px-4">Version</th>
                <th className="py-2.5 px-4">Effective Date</th>
                <th className="py-2.5 px-4">Published By</th>
                <th className="py-2.5 px-4">Active Rules</th>
                <th className="py-2.5 px-4">Key Amendments & Changelog</th>
                <th className="py-2.5 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {policyVersions.map((pv) => (
                <tr key={pv.version} className="hover:bg-slate-50/60 transition-colors">
                  <td className="py-3 px-4 font-mono font-semibold text-slate-900">
                    {pv.version}
                  </td>
                  <td className="py-3 px-4 font-mono text-slate-600">
                    {pv.effectiveDate}
                  </td>
                  <td className="py-3 px-4 text-slate-700">
                    {pv.publishedBy}
                  </td>
                  <td className="py-3 px-4 font-mono text-slate-900">
                    {pv.rulesCount} rules
                  </td>
                  <td className="py-3 px-4 text-slate-600 max-w-sm">
                    {pv.changelog}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button
                      onClick={() => setActiveVersion(pv.version)}
                      className={`px-2.5 py-1 text-[11px] font-medium rounded border transition-colors ${
                        activeVersion === pv.version
                          ? 'bg-slate-900 text-white border-slate-900'
                          : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                      }`}
                    >
                      {activeVersion === pv.version ? 'Active' : 'Evaluate Claims'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Edit Rule Modal */}
      {editingRule && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-lg border border-slate-200 shadow-xl max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-bold text-slate-900">
                Edit Policy Rule: {editingRule.code}
              </h3>
              <button
                onClick={() => setEditingRule(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  Rule Title
                </label>
                <input
                  type="text"
                  value={editingRule.title}
                  onChange={(e) => setEditingRule({ ...editingRule, title: e.target.value })}
                  className="w-full h-8 px-2.5 bg-slate-50 border border-slate-200 rounded text-slate-800 focus:outline-none focus:border-slate-400 focus:bg-white"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  Rule Logic Formula
                </label>
                <input
                  type="text"
                  value={editingRule.ruleLogic}
                  onChange={(e) => setEditingRule({ ...editingRule, ruleLogic: e.target.value })}
                  className="w-full h-8 px-2.5 font-mono bg-slate-50 border border-slate-200 rounded text-slate-800 focus:outline-none focus:border-slate-400 focus:bg-white"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  Source Clause Citation
                </label>
                <input
                  type="text"
                  value={editingRule.clauseCitation}
                  onChange={(e) => setEditingRule({ ...editingRule, clauseCitation: e.target.value })}
                  className="w-full h-8 px-2.5 bg-slate-50 border border-slate-200 rounded text-slate-800 focus:outline-none focus:border-slate-400 focus:bg-white"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  Limit Amount (INR ₹)
                </label>
                <input
                  type="number"
                  value={editingRule.limitAmount || 0}
                  onChange={(e) => setEditingRule({ ...editingRule, limitAmount: Number(e.target.value) })}
                  className="w-full h-8 px-2.5 font-mono bg-slate-50 border border-slate-200 rounded text-slate-800 focus:outline-none focus:border-slate-400 focus:bg-white"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setEditingRule(null)}
                className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveRule}
                className="px-4 py-1.5 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded shadow-xs"
              >
                Save & Update Rule
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
