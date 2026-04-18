/**
 * Unit Tests: AgentScoreCard Component
 *
 * Tests rendering, score display, breakdown visualization, compact mode,
 * recommended state, and assignment actions.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';

import AgentScoreCard, { AgentScoreMini } from '../AgentScoreCard';

// ── Test Data ────────────────────────────────────────────────────────────

const mockScoreBreakdown = {
  expertise: { raw: 35, max: 40, percentage: 87.5 },
  workload: { raw: 25, max: 30, percentage: 83.3, current_tickets: 3 },
  performance: { raw: 18, max: 20, percentage: 90.0 },
  response_time: { raw: 12, max: 15, percentage: 80.0 },
  availability: { raw: 10, max: 10, percentage: 100.0 },
};

const mockExplanations = {
  expertise: 'Direct specialty match: billing',
  workload: 'Optimal workload: 3 open tickets',
  performance: 'Excellent resolution rate: 95%',
  response_time: 'Excellent SLA compliance: 98%',
  availability: 'Agent is active and available',
};

const defaultProps = {
  agentId: 'agent-123',
  agentName: 'Test Agent',
  score: 0.85,
  rawScore: 97.75,
  scoreBreakdown: mockScoreBreakdown,
};

// ── Test Suite ────────────────────────────────────────────────────────────

describe('AgentScoreCard Component', () => {
  // ── Full Card Rendering ───────────────────────────────────────────────

  describe('Full Card Rendering', () => {
    it('renders agent name', () => {
      render(<AgentScoreCard {...defaultProps} />);
      expect(screen.getByText('Test Agent')).toBeInTheDocument();
    });

    it('renders score as percentage', () => {
      render(<AgentScoreCard {...defaultProps} />);
      expect(screen.getByText('85%')).toBeInTheDocument();
    });

    it('renders raw score', () => {
      render(<AgentScoreCard {...defaultProps} />);
      expect(screen.getByText(/97.8 \/ 115 pts/)).toBeInTheDocument();
    });

    it('renders open tickets count', () => {
      render(<AgentScoreCard {...defaultProps} />);
      expect(screen.getByText('3 open tickets')).toBeInTheDocument();
    });

    it('renders all 5 factor breakdowns', () => {
      const { container } = render(<AgentScoreCard {...defaultProps} />);
      
      // Check that breakdown section exists
      expect(screen.getByText('5-Factor Score Breakdown')).toBeInTheDocument();
      
      // Check factor labels are present
      const factorLabels = ['Expertise', 'Workload', 'Performance', 'Response Time', 'Availability'];
      factorLabels.forEach(label => {
        expect(screen.getByText(label)).toBeInTheDocument();
      });
    });

    it('renders breakdown percentages', () => {
      render(<AgentScoreCard {...defaultProps} />);
      
      // Check percentages (rounded)
      expect(screen.getByText('88%')).toBeInTheDocument();  // 87.5 -> 88
      expect(screen.getByText('83%')).toBeInTheDocument();  // 83.3 -> 83
      expect(screen.getByText('90%')).toBeInTheDocument();
      expect(screen.getByText('80%')).toBeInTheDocument();
      expect(screen.getByText('100%')).toBeInTheDocument();
    });
  });

  // ── Recommended State ─────────────────────────────────────────────────

  describe('Recommended State', () => {
    it('shows recommended badge when isRecommended is true', () => {
      render(<AgentScoreCard {...defaultProps} isRecommended={true} />);
      expect(screen.getByText('Recommended')).toBeInTheDocument();
    });

    it('does not show recommended badge by default', () => {
      render(<AgentScoreCard {...defaultProps} />);
      expect(screen.queryByText('Recommended')).not.toBeInTheDocument();
    });

    it('shows emerald gradient background for recommended agents', () => {
      const { container } = render(<AgentScoreCard {...defaultProps} isRecommended={true} />);
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('from-emerald-500/10');
    });

    it('shows "Assign Best Match" button for recommended agents', () => {
      const onAssign = jest.fn();
      render(
        <AgentScoreCard {...defaultProps} isRecommended={true} onAssign={onAssign} />
      );
      expect(screen.getByText('Assign Best Match')).toBeInTheDocument();
    });
  });

  // ── Explanations ─────────────────────────────────────────────────────

  describe('Explanations', () => {
    it('renders explanations when provided', () => {
      render(
        <AgentScoreCard {...defaultProps} explanations={mockExplanations} />
      );
      
      expect(screen.getByText(/Direct specialty match: billing/)).toBeInTheDocument();
      expect(screen.getByText(/Optimal workload: 3 open tickets/)).toBeInTheDocument();
      expect(screen.getByText(/Excellent resolution rate: 95%/)).toBeInTheDocument();
    });

    it('does not render explanations section when not provided', () => {
      render(<AgentScoreCard {...defaultProps} />);
      
      // Should not have the explanation container
      const explanationElements = screen.queryAllByText(/Expertise:/);
      expect(explanationElements.length).toBe(0);
    });
  });

  // ── Compact Mode ─────────────────────────────────────────────────────

  describe('Compact Mode', () => {
    it('renders in compact mode with correct structure', () => {
      const { container } = render(
        <AgentScoreCard {...defaultProps} compact={true} />
      );
      
      expect(screen.getByText('Test Agent')).toBeInTheDocument();
      expect(screen.getByText('85%')).toBeInTheDocument();
      expect(screen.getByText('3 open tickets')).toBeInTheDocument();
    });

    it('shows rank in compact mode', () => {
      render(
        <AgentScoreCard {...defaultProps} compact={true} rank={1} />
      );
      
      expect(screen.getByText('1')).toBeInTheDocument();
    });

    it('shows "Best" badge for recommended agents in compact mode', () => {
      render(
        <AgentScoreCard {...defaultProps} compact={true} isRecommended={true} />
      );
      
      expect(screen.getByText('Best')).toBeInTheDocument();
    });

    it('does not show score breakdown in compact mode', () => {
      render(<AgentScoreCard {...defaultProps} compact={true} />);
      
      expect(screen.queryByText('5-Factor Score Breakdown')).not.toBeInTheDocument();
    });
  });

  // ── Assignment Action ────────────────────────────────────────────────

  describe('Assignment Action', () => {
    it('renders assign button when onAssign is provided', () => {
      const onAssign = jest.fn();
      render(<AgentScoreCard {...defaultProps} onAssign={onAssign} />);
      
      expect(screen.getByText('Assign to Agent')).toBeInTheDocument();
    });

    it('does not render assign button when onAssign is not provided', () => {
      render(<AgentScoreCard {...defaultProps} />);
      
      expect(screen.queryByText('Assign to Agent')).not.toBeInTheDocument();
    });

    it('calls onAssign with agentId when button clicked', () => {
      const onAssign = jest.fn();
      render(<AgentScoreCard {...defaultProps} onAssign={onAssign} />);
      
      fireEvent.click(screen.getByText('Assign to Agent'));
      expect(onAssign).toHaveBeenCalledWith('agent-123');
    });

    it('works in compact mode', () => {
      const onAssign = jest.fn();
      render(
        <AgentScoreCard {...defaultProps} compact={true} onAssign={onAssign} />
      );
      
      fireEvent.click(screen.getByText('Assign'));
      expect(onAssign).toHaveBeenCalledWith('agent-123');
    });
  });

  // ── Score Colors ─────────────────────────────────────────────────────

  describe('Score Colors', () => {
    it('applies emerald color for high scores (>=0.8)', () => {
      const { container } = render(
        <AgentScoreCard {...defaultProps} score={0.85} />
      );
      expect(container.querySelector('.text-emerald-400')).toBeInTheDocument();
    });

    it('applies yellow color for good scores (0.6-0.8)', () => {
      const { container } = render(
        <AgentScoreCard {...defaultProps} score={0.7} />
      );
      expect(container.querySelector('.text-yellow-400')).toBeInTheDocument();
    });

    it('applies orange color for medium scores (0.4-0.6)', () => {
      const { container } = render(
        <AgentScoreCard {...defaultProps} score={0.5} />
      );
      expect(container.querySelector('.text-orange-400')).toBeInTheDocument();
    });

    it('applies red color for low scores (<0.4)', () => {
      const { container } = render(
        <AgentScoreCard {...defaultProps} score={0.3} />
      );
      expect(container.querySelector('.text-red-400')).toBeInTheDocument();
    });
  });

  // ── Rank Display ─────────────────────────────────────────────────────

  describe('Rank Display', () => {
    it('renders rank number', () => {
      render(<AgentScoreCard {...defaultProps} rank={2} />);
      expect(screen.getByText('2')).toBeInTheDocument();
    });

    it('applies orange styling for rank 1', () => {
      const { container } = render(<AgentScoreCard {...defaultProps} rank={1} />);
      expect(container.querySelector('.bg-orange-500\\/20')).toBeInTheDocument();
    });

    it('applies default styling for other ranks', () => {
      const { container } = render(<AgentScoreCard {...defaultProps} rank={3} />);
      // Rank 3 should have neutral styling
      const rankElement = screen.getByText('3');
      expect(rankElement).toBeInTheDocument();
    });
  });

  // ── Custom className ─────────────────────────────────────────────────

  describe('Custom className', () => {
    it('applies custom className to the card', () => {
      const { container } = render(
        <AgentScoreCard {...defaultProps} className="my-custom-class" />
      );
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('my-custom-class');
    });
  });
});

// ── AgentScoreMini Tests ───────────────────────────────────────────────────

describe('AgentScoreMini Component', () => {
  it('renders agent name', () => {
    render(<AgentScoreMini score={0.75} agentName="Mini Agent" />);
    expect(screen.getByText('Mini Agent')).toBeInTheDocument();
  });

  it('renders score percentage', () => {
    render(<AgentScoreMini score={0.75} agentName="Mini Agent" />);
    expect(screen.getByText('75%')).toBeInTheDocument();
  });

  it('applies emerald dot for high scores', () => {
    const { container } = render(
      <AgentScoreMini score={0.85} agentName="High Score" />
    );
    expect(container.querySelector('.bg-emerald-500')).toBeInTheDocument();
  });

  it('applies yellow dot for good scores', () => {
    const { container } = render(
      <AgentScoreMini score={0.65} agentName="Good Score" />
    );
    expect(container.querySelector('.bg-yellow-500')).toBeInTheDocument();
  });

  it('applies orange dot for medium scores', () => {
    const { container } = render(
      <AgentScoreMini score={0.45} agentName="Medium Score" />
    );
    expect(container.querySelector('.bg-orange-500')).toBeInTheDocument();
  });

  it('applies red dot for low scores', () => {
    const { container } = render(
      <AgentScoreMini score={0.25} agentName="Low Score" />
    );
    expect(container.querySelector('.bg-red-500')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <AgentScoreMini score={0.5} agentName="Custom" className="custom-mini" />
    );
    expect(container.firstChild).toHaveClass('custom-mini');
  });
});

// ── Edge Cases ─────────────────────────────────────────────────────────────

describe('Edge Cases', () => {
  it('handles zero score', () => {
    render(
      <AgentScoreCard
        {...defaultProps}
        score={0}
        rawScore={0}
      />
    );
    expect(screen.getByText('0%')).toBeInTheDocument();
  });

  it('handles perfect score (1.0)', () => {
    render(
      <AgentScoreCard
        {...defaultProps}
        score={1.0}
        rawScore={115}
      />
    );
    // Use getAllByText since 100% appears multiple times (main score + breakdowns)
    const elements = screen.getAllByText('100%');
    expect(elements.length).toBeGreaterThan(0);
  });

  it('handles zero open tickets', () => {
    render(
      <AgentScoreCard
        {...defaultProps}
        scoreBreakdown={{
          ...mockScoreBreakdown,
          workload: { ...mockScoreBreakdown.workload, current_tickets: 0 },
        }}
      />
    );
    expect(screen.getByText('0 open tickets')).toBeInTheDocument();
  });

  it('handles high ticket count', () => {
    render(
      <AgentScoreCard
        {...defaultProps}
        scoreBreakdown={{
          ...mockScoreBreakdown,
          workload: { ...mockScoreBreakdown.workload, current_tickets: 99 },
        }}
      />
    );
    expect(screen.getByText('99 open tickets')).toBeInTheDocument();
  });

  it('handles very long agent name', () => {
    render(
      <AgentScoreCard
        {...defaultProps}
        agentName="This is a very long agent name that should be truncated"
      />
    );
    // Should still render without crashing
    expect(screen.getByText(/This is a very long/)).toBeInTheDocument();
  });
});
