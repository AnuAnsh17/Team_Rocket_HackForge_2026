import React from 'react';
import {
  LayoutDashboard,
  CheckSquare,
  SearchCode,
  Copy,
  BarChart3,
  GitPullRequest,
  Users,
  BookOpen,
  FileSpreadsheet,
  ChevronLeft,
  ChevronRight,
  Shield,
  AlertTriangle,
  Sparkles,
} from 'lucide-react';
import { ActiveTab, Claim } from '../types';

interface SidebarProps {
  activeTab: ActiveTab;
  onNavigate: (tab: ActiveTab) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  claims: Claim[];
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onNavigate,
  collapsed,
  onToggleCollapse,
  claims,
}) => {
  const pendingReviewCount = claims.filter((c) => c.status === 'UNKNOWN').length;
  const violationCount = claims.filter((c) => c.status === 'FAIL').length;
  const duplicateCount = claims.filter((c) => c.issueType === 'DUPLICATE_CANDIDATE').length;

  const navSections = [
    {
      title: 'OVERVIEW',
      items: [
        {
          id: 'landing' as ActiveTab,
          label: '3D Product Tour',
          icon: Sparkles,
          badge: '3D',
          badgeColor: 'bg-blue-50 text-blue-700 font-semibold',
        },
        {
          id: 'overview' as ActiveTab,
          label: 'Overview Dashboard',
          icon: LayoutDashboard,
          badge: null,
        },
      ],
    },
    {
      title: 'AUDIT & TRIAGE',
      items: [
        {
          id: 'audit-queue' as ActiveTab,
          label: 'AI Audit Queue',
          icon: CheckSquare,
          badge: pendingReviewCount + violationCount > 0 ? `${pendingReviewCount + violationCount}` : null,
          badgeColor: 'bg-amber-100 text-amber-800',
        },
        {
          id: 'workbench' as ActiveTab,
          label: 'Investigation Workbench',
          icon: SearchCode,
          badge: null,
        },
        {
          id: 'duplicates' as ActiveTab,
          label: 'Duplicate & Anomaly Review',
          icon: Copy,
          badge: duplicateCount > 0 ? `${duplicateCount}` : null,
          badgeColor: 'bg-rose-100 text-rose-800',
        },
      ],
    },
    {
      title: 'INTELLIGENCE',
      items: [
        {
          id: 'spending-analytics' as ActiveTab,
          label: 'Spending & Budget Analytics',
          icon: BarChart3,
          badge: null,
        },
        {
          id: 'approvals' as ActiveTab,
          label: 'Approvals & Reimbursements',
          icon: GitPullRequest,
          badge: '22',
          badgeColor: 'bg-slate-100 text-slate-700',
        },
        {
          id: 'employee-merchants' as ActiveTab,
          label: 'Employee & Merchant Profiles',
          icon: Users,
          badge: null,
        },
      ],
    },
    {
      title: 'GOVERNANCE',
      items: [
        {
          id: 'policy-studio' as ActiveTab,
          label: 'Policy Studio',
          icon: BookOpen,
          badge: '7 Rules',
          badgeColor: 'bg-emerald-50 text-emerald-700',
        },
        {
          id: 'audit-trail' as ActiveTab,
          label: 'Audit Trail & Exports',
          icon: FileSpreadsheet,
          badge: null,
        },
      ],
    },
  ];

  return (
    <aside
      className={`relative flex flex-col border-r border-slate-200 bg-white transition-all duration-200 z-20 shrink-0 ${
        collapsed ? 'w-14' : 'w-64'
      }`}
    >
      {/* Navigation Body */}
      <div className="flex-1 overflow-y-auto py-3 px-2">
        {navSections.map((section, sIdx) => (
          <div key={section.title} className={sIdx > 0 ? 'mt-5' : ''}>
            {!collapsed && (
              <div className="px-3 pb-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                {section.title}
              </div>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => onNavigate(item.id)}
                    title={collapsed ? item.label : undefined}
                    className={`group w-full flex items-center gap-2.5 px-3 py-2 text-xs rounded transition-colors ${
                      isActive
                        ? 'bg-slate-900 text-white font-medium shadow-xs'
                        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                    }`}
                  >
                    <Icon
                      className={`h-4 w-4 shrink-0 transition-colors ${
                        isActive
                          ? 'text-white'
                          : 'text-slate-400 group-hover:text-slate-700'
                      }`}
                    />
                    {!collapsed && (
                      <span className="truncate flex-1 text-left">
                        {item.label}
                      </span>
                    )}
                    {!collapsed && item.badge && (
                      <span
                        className={`text-[10px] font-mono font-medium px-1.5 py-0.5 rounded ${
                          isActive
                            ? 'bg-slate-800 text-slate-200'
                            : item.badgeColor || 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Collapse Footer Toggle */}
      <div className="p-2 border-t border-slate-200 bg-slate-50/50">
        <button
          onClick={onToggleCollapse}
          className="w-full flex items-center justify-center gap-2 py-1.5 px-2 text-xs text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded transition-colors"
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <>
              <ChevronLeft className="h-4 w-4" />
              <span className="text-[11px] font-medium">Collapse Sidebar</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
};
