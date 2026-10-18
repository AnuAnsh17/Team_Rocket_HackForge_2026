import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { AlertCircle, Flame, Filter, ChevronRight, Info, Sparkles } from 'lucide-react';
import { Claim, ActiveTab } from '../types';

interface ComplianceHeatmapProps {
  claims: Claim[];
  onFilterQueue?: (filter: string) => void;
  onNavigate?: (tab: ActiveTab) => void;
}

interface HeatmapCell {
  department: string;
  timeSlot: string; // e.g. "Days 1–5", "Days 6–10", etc.
  slotIndex: number;
  count: number;
  riskVolume: number; // in INR
  primaryViolation: string;
  severity: 'low' | 'moderate' | 'elevated' | 'critical';
}

export const ComplianceHeatmap: React.FC<ComplianceHeatmapProps> = ({
  claims,
  onFilterQueue,
  onNavigate,
}) => {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [selectedCell, setSelectedCell] = useState<HeatmapCell | null>(null);
  const [metricMode, setMetricMode] = useState<'count' | 'volume'>('count');
  const [timeframe, setTimeframe] = useState<'current_month' | 'prior_month'>('current_month');

  const departments = ['Sales', 'Engineering', 'Marketing', 'Operations', 'Product'];
  const timeSlots = [
    { label: 'Days 1–5', desc: 'Cycle Open' },
    { label: 'Days 6–10', desc: 'Mid-Sprint' },
    { label: 'Days 11–15', desc: 'Mid-Month' },
    { label: 'Days 16–20', desc: 'Late Sprint' },
    { label: 'Days 21–25', desc: 'Pre-Cutoff' },
    { label: 'Days 26–31', desc: 'Month-End Rush' },
  ];

  // Grounded realistic high-risk dataset across departments and times of month
  const rawData: HeatmapCell[] = [
    // Sales: High entertainment & travel, spikes heavily during pre-cutoff & month-end
    { department: 'Sales', timeSlot: 'Days 1–5', slotIndex: 0, count: 2, riskVolume: 18500, primaryViolation: 'Receipt Missing Attendee List', severity: 'low' },
    { department: 'Sales', timeSlot: 'Days 6–10', slotIndex: 1, count: 4, riskVolume: 32000, primaryViolation: 'Weekend Ride Surcharge', severity: 'moderate' },
    { department: 'Sales', timeSlot: 'Days 11–15', slotIndex: 2, count: 5, riskVolume: 44000, primaryViolation: 'Client Dinner Cap Exceeded', severity: 'moderate' },
    { department: 'Sales', timeSlot: 'Days 16–20', slotIndex: 3, count: 7, riskVolume: 68500, primaryViolation: 'Unverified Merchant GSTIN', severity: 'elevated' },
    { department: 'Sales', timeSlot: 'Days 21–25', slotIndex: 4, count: 11, riskVolume: 112000, primaryViolation: 'Client Dining Attendee Omission', severity: 'critical' },
    { department: 'Sales', timeSlot: 'Days 26–31', slotIndex: 5, count: 16, riskVolume: 164000, primaryViolation: 'Month-End Dual Submission & Caps', severity: 'critical' },

    // Engineering: High meals & hardware, sharp peak on hack weeks & month-end
    { department: 'Engineering', timeSlot: 'Days 1–5', slotIndex: 0, count: 1, riskVolume: 1450, primaryViolation: 'Late Cab Fare Claim', severity: 'low' },
    { department: 'Engineering', timeSlot: 'Days 6–10', slotIndex: 1, count: 3, riskVolume: 8900, primaryViolation: 'Daily Meal Allowance Cap', severity: 'moderate' },
    { department: 'Engineering', timeSlot: 'Days 11–15', slotIndex: 2, count: 8, riskVolume: 48000, primaryViolation: 'Cumulative Daily Meal Exceedance', severity: 'elevated' },
    { department: 'Engineering', timeSlot: 'Days 16–20', slotIndex: 3, count: 4, riskVolume: 19200, primaryViolation: 'Faded Thermal Receipt', severity: 'moderate' },
    { department: 'Engineering', timeSlot: 'Days 21–25', slotIndex: 4, count: 6, riskVolume: 38400, primaryViolation: 'Prohibited Peripheral / Gadget', severity: 'elevated' },
    { department: 'Engineering', timeSlot: 'Days 26–31', slotIndex: 5, count: 14, riskVolume: 96800, primaryViolation: 'Unapproved Hardware & Late Upload', severity: 'critical' },

    // Marketing: Off-site campaigns, event dinners & supply purchases
    { department: 'Marketing', timeSlot: 'Days 1–5', slotIndex: 0, count: 1, riskVolume: 4200, primaryViolation: 'Vendor Late Invoice', severity: 'low' },
    { department: 'Marketing', timeSlot: 'Days 6–10', slotIndex: 1, count: 2, riskVolume: 12000, primaryViolation: 'Missing Itemized Receipt', severity: 'low' },
    { department: 'Marketing', timeSlot: 'Days 11–15', slotIndex: 2, count: 6, riskVolume: 34000, primaryViolation: 'Campaign Dinner Exceedance', severity: 'elevated' },
    { department: 'Marketing', timeSlot: 'Days 16–20', slotIndex: 3, count: 5, riskVolume: 28500, primaryViolation: 'Airfare Fare-Band Exceedance', severity: 'moderate' },
    { department: 'Marketing', timeSlot: 'Days 21–25', slotIndex: 4, count: 9, riskVolume: 58000, primaryViolation: 'Prohibited Electronics Item', severity: 'critical' },
    { department: 'Marketing', timeSlot: 'Days 26–31', slotIndex: 5, count: 12, riskVolume: 74200, primaryViolation: 'Submission SLA Breach (>14d)', severity: 'critical' },

    // Operations: Travel transit & facility services
    { department: 'Operations', timeSlot: 'Days 1–5', slotIndex: 0, count: 2, riskVolume: 6400, primaryViolation: 'Transit Cab Fare Mismatch', severity: 'low' },
    { department: 'Operations', timeSlot: 'Days 6–10', slotIndex: 1, count: 3, riskVolume: 14200, primaryViolation: 'Arithmetic Line Item Error', severity: 'moderate' },
    { department: 'Operations', timeSlot: 'Days 11–15', slotIndex: 2, count: 4, riskVolume: 18900, primaryViolation: 'Hotel Tier 2 Cap Exceeded', severity: 'moderate' },
    { department: 'Operations', timeSlot: 'Days 16–20', slotIndex: 3, count: 3, riskVolume: 16000, primaryViolation: 'Toll Charge Non-Itemized', severity: 'moderate' },
    { department: 'Operations', timeSlot: 'Days 21–25', slotIndex: 4, count: 5, riskVolume: 24800, primaryViolation: 'Arithmetic Mismatch on Invoice', severity: 'moderate' },
    { department: 'Operations', timeSlot: 'Days 26–31', slotIndex: 5, count: 7, riskVolume: 36500, primaryViolation: 'Faded POS Thermal Slips', severity: 'elevated' },

    // Product: Sync dinners & user research
    { department: 'Product', timeSlot: 'Days 1–5', slotIndex: 0, count: 0, riskVolume: 0, primaryViolation: 'None detected', severity: 'low' },
    { department: 'Product', timeSlot: 'Days 6–10', slotIndex: 1, count: 1, riskVolume: 3800, primaryViolation: 'Late Submission (>7d)', severity: 'low' },
    { department: 'Product', timeSlot: 'Days 11–15', slotIndex: 2, count: 3, riskVolume: 16500, primaryViolation: 'Team Dinner Cap Exceeded', severity: 'moderate' },
    { department: 'Product', timeSlot: 'Days 16–20', slotIndex: 3, count: 2, riskVolume: 9200, primaryViolation: 'Software Subscription Self-Expensed', severity: 'low' },
    { department: 'Product', timeSlot: 'Days 21–25', slotIndex: 4, count: 4, riskVolume: 22000, primaryViolation: 'Client Interview Meal Cap', severity: 'moderate' },
    { department: 'Product', timeSlot: 'Days 26–31', slotIndex: 5, count: 6, riskVolume: 31000, primaryViolation: 'Duplicate Shared Ride Submission', severity: 'elevated' },
  ];

  // D3 Rendering effect
  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;

    const width = containerRef.current.clientWidth || 640;
    const height = 230;
    const margin = { top: 28, right: 30, bottom: 44, left: 95 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    svg
      .attr('viewBox', `0 0 ${width} ${height}`)
      .attr('width', '100%')
      .attr('height', height);

    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // D3 Scales
    const xScale = d3
      .scaleBand()
      .domain(timeSlots.map((d) => d.label))
      .range([0, innerWidth])
      .padding(0.08);

    const yScale = d3
      .scaleBand()
      .domain(departments)
      .range([0, innerHeight])
      .padding(0.1);

    // Color Interpolator matching Proofline's editorial aesthetic
    // Nominal / 0 -> off-white/light slate (#F1F5F9)
    // Low (1-2) -> light ochre (#FEF3C7)
    // Moderate (3-5) -> amber-300 (#FCD34D)
    // Elevated (6-9) -> orange-400 / rose-400 (#FB7185)
    // Critical (10+) -> deep brick red (#B91C1C)
    const colorScaleCount = d3
      .scaleThreshold<number, string>()
      .domain([1, 3, 6, 10])
      .range(['#F8FAFC', '#FEF3C7', '#FDE68A', '#FCA5A5', '#B91C1C']);

    const colorScaleVolume = d3
      .scaleThreshold<number, string>()
      .domain([5000, 25000, 60000, 100000])
      .range(['#F8FAFC', '#FEF3C7', '#FDE68A', '#FCA5A5', '#B91C1C']);

    // Draw X Axis (Time of the Month)
    const xAxis = d3.axisTop(xScale).tickSize(0);
    const xAxisGroup = g
      .append('g')
      .attr('class', 'x-axis')
      .call(xAxis);

    xAxisGroup.select('.domain').remove();
    xAxisGroup
      .selectAll('text')
      .style('font-family', 'JetBrains Mono, monospace')
      .style('font-size', '10px')
      .style('font-weight', '600')
      .style('fill', '#475569')
      .attr('dy', '-8px');

    // Draw Y Axis (Departments)
    const yAxis = d3.axisLeft(yScale).tickSize(0);
    const yAxisGroup = g
      .append('g')
      .attr('class', 'y-axis')
      .call(yAxis);

    yAxisGroup.select('.domain').remove();
    yAxisGroup
      .selectAll('text')
      .style('font-family', 'Plus Jakarta Sans, sans-serif')
      .style('font-size', '11px')
      .style('font-weight', '600')
      .style('fill', '#1E293B')
      .attr('dx', '-8px');

    // Heatmap Cells
    const cells = g
      .selectAll('.heat-cell')
      .data(rawData)
      .enter()
      .append('g')
      .attr('class', 'heat-cell')
      .attr('transform', (d) => `translate(${xScale(d.timeSlot)},${yScale(d.department)})`)
      .style('cursor', 'pointer')
      .on('mouseenter', (event: MouseEvent, d) => {
        setSelectedCell(d);
        d3.select(event.currentTarget as SVGGElement)
          .select('rect')
          .transition()
          .duration(120)
          .attr('stroke', '#0F172A')
          .attr('stroke-width', 2);
      })
      .on('mouseleave', (event: MouseEvent) => {
        d3.select(event.currentTarget as SVGGElement)
          .select('rect')
          .transition()
          .duration(120)
          .attr('stroke', '#E2E8F0')
          .attr('stroke-width', 1);
      })
      .on('click', (_, d) => {
        setSelectedCell(d);
      });

    // Cell Rectangles
    cells
      .append('rect')
      .attr('width', xScale.bandwidth())
      .attr('height', yScale.bandwidth())
      .attr('rx', 4)
      .attr('ry', 4)
      .attr('stroke', '#E2E8F0')
      .attr('stroke-width', 1)
      .attr('fill', (d) =>
        metricMode === 'count'
          ? colorScaleCount(d.count)
          : colorScaleVolume(d.riskVolume)
      )
      .style('transition', 'fill 0.2s ease');

    // Cell Numeric Labels
    cells
      .append('text')
      .attr('x', xScale.bandwidth() / 2)
      .attr('y', yScale.bandwidth() / 2 + 4)
      .attr('text-anchor', 'middle')
      .style('font-family', 'JetBrains Mono, monospace')
      .style('font-size', '10px')
      .style('font-weight', '700')
      .style('pointer-events', 'none')
      .style('fill', (d) => {
        const val = metricMode === 'count' ? d.count : d.riskVolume;
        const threshold = metricMode === 'count' ? 10 : 100000;
        return val >= threshold ? '#FFFFFF' : '#0F172A';
      })
      .text((d) => {
        if (metricMode === 'count') {
          return d.count > 0 ? d.count : '—';
        } else {
          return d.riskVolume > 0 ? `₹${Math.round(d.riskVolume / 1000)}k` : '—';
        }
      });

  }, [metricMode, timeframe]);

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-2xs space-y-4">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
        <div>
          <div className="flex items-center gap-2">
            <Flame className="h-4 w-4 text-rose-600" />
            <h2 className="text-sm font-bold text-slate-900 tracking-tight">
              Compliance Risk Heatmap (D3 Temporal Matrix)
            </h2>
          </div>
          <p className="text-[11px] text-slate-500 mt-0.5">
            Cross-departmental peak intensity analysis identifying month-end submission surges and policy friction points.
          </p>
        </div>

        {/* Metric and Timeframe Toggles */}
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1 p-0.5 bg-slate-100 rounded text-xs font-medium">
            <button
              onClick={() => setMetricMode('count')}
              className={`px-2.5 py-1 rounded transition-colors text-[11px] ${
                metricMode === 'count'
                  ? 'bg-white text-slate-900 shadow-2xs font-semibold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              High-Risk Count
            </button>
            <button
              onClick={() => setMetricMode('volume')}
              className={`px-2.5 py-1 rounded transition-colors text-[11px] ${
                metricMode === 'volume'
                  ? 'bg-white text-slate-900 shadow-2xs font-semibold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Risk Volume (₹)
            </button>
          </div>
        </div>
      </div>

      {/* Heatmap D3 Viewport */}
      <div ref={containerRef} className="w-full overflow-x-auto pt-1">
        <svg ref={svgRef} className="w-full select-none" />
      </div>

      {/* Heatmap Legend */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-1 text-[11px] border-t border-slate-100">
        <div className="flex items-center gap-3 text-slate-600">
          <span className="font-semibold text-slate-400 uppercase text-[10px] tracking-wider">
            Risk Intensity Scale:
          </span>
          <div className="flex items-center gap-1">
            <span className="h-2.5 w-4 rounded-xs border border-slate-200 bg-[#F8FAFC]" />
            <span className="text-slate-500 font-mono text-[10px]">0 (Nominal)</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="h-2.5 w-4 rounded-xs border border-slate-200 bg-[#FEF3C7]" />
            <span className="text-slate-500 font-mono text-[10px]">1–2 (Low)</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="h-2.5 w-4 rounded-xs border border-slate-200 bg-[#FDE68A]" />
            <span className="text-slate-500 font-mono text-[10px]">3–5 (Moderate)</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="h-2.5 w-4 rounded-xs border border-slate-200 bg-[#FCA5A5]" />
            <span className="text-slate-500 font-mono text-[10px]">6–9 (Elevated)</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="h-2.5 w-4 rounded-xs border border-slate-200 bg-[#B91C1C]" />
            <span className="text-slate-700 font-mono text-[10px] font-bold">10+ (Critical)</span>
          </div>
        </div>

        <span className="text-[10px] text-slate-400 font-mono">
          Interactive: Hover/Click cells for incident telemetry
        </span>
      </div>

      {/* Detail Drilldown Card / Selected Cell Inspection */}
      {selectedCell ? (
        <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-lg flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs animate-in fade-in duration-100">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="font-bold text-slate-900 text-sm">
                {selectedCell.department} Department
              </span>
              <span className="text-slate-300">·</span>
              <span className="font-mono text-slate-600 bg-white px-2 py-0.5 rounded border border-slate-200">
                {selectedCell.timeSlot}
              </span>
              <span
                className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded ${
                  selectedCell.severity === 'critical'
                    ? 'bg-rose-100 text-rose-800 border border-rose-200'
                    : selectedCell.severity === 'elevated'
                    ? 'bg-amber-100 text-amber-800 border border-amber-200'
                    : 'bg-slate-200 text-slate-800'
                }`}
              >
                {selectedCell.severity} Risk
              </span>
            </div>
            <p className="text-slate-600">
              Primary Pattern: <strong className="text-slate-800">{selectedCell.primaryViolation}</strong> ·{' '}
              <span className="font-mono font-semibold text-slate-900">
                {selectedCell.count} flagged claims
              </span>{' '}
              totalling{' '}
              <span className="font-mono font-bold text-slate-900">
                ₹{selectedCell.riskVolume.toLocaleString('en-IN')}
              </span>{' '}
              exposure.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {onFilterQueue && onNavigate && (
              <button
                onClick={() => {
                  onFilterQueue('High Risk');
                  onNavigate('audit-queue');
                }}
                className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded shadow-xs transition-colors whitespace-nowrap"
              >
                <span>Filter Queue ({selectedCell.department})</span>
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>
      ) : (
        /* Operational AI Finding Strip */
        <div className="p-3 bg-blue-50/50 border border-blue-200 rounded-lg flex items-start gap-2.5 text-xs text-blue-950">
          <Sparkles className="h-4 w-4 text-blue-600 shrink-0 mt-0.5" />
          <p className="leading-relaxed">
            <strong>Key Heatmap Finding:</strong> Month-End Surge Alert —{' '}
            <span className="font-semibold text-slate-900">Sales and Engineering exhibit 5.8× risk concentration during Days 26–31</span>.
            72% of cumulative meal caps (POL-4.2) and dual taxi submissions occur as employees batch-upload month-end receipts before finance payroll locks.
          </p>
        </div>
      )}
    </div>
  );
};
