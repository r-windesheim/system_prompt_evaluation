"""
Interactive HTML Report Generator
Creates self-contained HTML reports with embedded data and interactive charts
"""

import json
import base64
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots


def generate_executive_summary(
    scores: Dict[str, float],
    quirks: List[Dict[str, Any]],
    config_name: str,
    section_count: int
) -> str:
    """
    Generate an AI-style executive summary

    Args:
        scores: Dimension scores
        quirks: Detected quirks
        config_name: Configuration name
        section_count: Number of sections

    Returns:
        HTML string with executive summary
    """
    avg_score = sum(scores.values()) / len(scores) if scores else 0

    # Determine performance level
    if avg_score > 80:
        performance = "exceptional"
        emoji = "🌟"
    elif avg_score > 60:
        performance = "strong"
        emoji = "✅"
    elif avg_score > 40:
        performance = "moderate"
        emoji = "📊"
    else:
        performance = "developing"
        emoji = "📈"

    # Find top dimensions
    sorted_dims = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_dims = [dim for dim, _ in sorted_dims[:2]]
    weak_dims = [dim for dim, _ in sorted_dims[-2:] if scores[dim] < 50]

    # Count significant quirks
    significant_quirks = [q for q in quirks if q.get('significant', False)]

    summary = f"""
    <div class="executive-summary">
        <h2>{emoji} Executive Summary</h2>

        <div class="summary-card">
            <p class="lead">
                Configuration <strong>{config_name}</strong> demonstrates <strong>{performance}</strong> overall performance
                with an average score of <strong>{avg_score:.1f}%</strong> across {len(scores)} evaluation dimensions.
            </p>

            <div class="key-findings">
                <h3>Key Findings</h3>
                <ul>
                    <li><strong>Strengths:</strong> Excels in {' and '.join(top_dims)} with scores above {scores[top_dims[0]]:.0f}%</li>
                    {"<li><strong>Improvement Areas:</strong> " + ' and '.join(weak_dims) + " show room for enhancement</li>" if weak_dims else ""}
                    <li><strong>Behavioral Profile:</strong> {len(quirks)} quirks detected, {len(significant_quirks)} statistically significant</li>
                    <li><strong>Complexity:</strong> Uses {section_count} prompt sections</li>
                </ul>
            </div>

            <div class="recommendations">
                <h3>Recommendations</h3>
                <ul>
                    {"<li>Consider simplifying the prompt - current configuration may be overly complex</li>" if section_count > 6 else ""}
                    {"<li>Focus on improving " + weak_dims[0] + " for better overall performance</li>" if weak_dims else ""}
                    {"<li>Strong quirk presence suggests reviewing behavioral instructions</li>" if len(significant_quirks) > 3 else ""}
                    {"<li>Current configuration is well-optimized - minor tweaks only</li>" if avg_score > 80 else ""}
                </ul>
            </div>
        </div>
    </div>
    """

    return summary


def create_performance_charts(df: pd.DataFrame) -> str:
    """
    Create interactive performance charts

    Args:
        df: DataFrame with evaluation results

    Returns:
        HTML string with embedded Plotly charts
    """
    # Create subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("Score Distribution", "Dimension Comparison", "Query Performance", "Response Metrics"),
        specs=[[{"type": "box"}, {"type": "bar"}],
               [{"type": "scatter"}, {"type": "scatter"}]]
    )

    # Extract dimensions from columns
    dimensions = [col for col in df.columns if 'evaluation_score' in col or 'score' in col]

    if dimensions:
        # Box plot of score distribution
        for dim in dimensions[:6]:  # Limit to 6 dimensions
            fig.add_trace(
                go.Box(y=df[dim], name=dim.replace('_score', ''), marker_color='#3b82f6'),
                row=1, col=1
            )

    # Bar chart of average scores by dimension
    if 'evaluation_question' in df.columns:
        avg_by_question = df.groupby('evaluation_question')['evaluation_score'].mean().sort_values(ascending=False)
        fig.add_trace(
            go.Bar(x=avg_by_question.values, y=avg_by_question.index, orientation='h',
                  marker_color='#8b5cf6'),
            row=1, col=2
        )

    # Scatter plot of scores over queries
    if 'test_query' in df.columns:
        query_avg = df.groupby('test_query')['evaluation_score'].mean()
        fig.add_trace(
            go.Scatter(x=list(range(len(query_avg))), y=query_avg.values,
                      mode='lines+markers', marker_color='#10b981'),
            row=2, col=1
        )

    # Response metrics
    if 'word_count' in df.columns and 'evaluation_score' in df.columns:
        fig.add_trace(
            go.Scatter(x=df['word_count'], y=df['evaluation_score'],
                      mode='markers', marker_color='#f59e0b', marker_size=8, opacity=0.6),
            row=2, col=2
        )

    # Update layout
    fig.update_layout(
        height=800,
        showlegend=False,
        template='plotly_dark',
        title_text="Performance Analysis Dashboard",
        font=dict(size=12)
    )

    # Convert to HTML
    chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

    return f"""
    <div class="charts-section">
        <h2>📊 Performance Analysis</h2>
        {chart_html}
    </div>
    """


def create_quirk_analysis_section(quirks: List[Dict[str, Any]]) -> str:
    """
    Create quirk analysis section

    Args:
        quirks: List of detected quirks

    Returns:
        HTML string with quirk analysis
    """
    if not quirks:
        return "<div class='quirks-section'><h2>🔍 Behavioral Analysis</h2><p>No significant quirks detected.</p></div>"

    quirk_html = """
    <div class="quirks-section">
        <h2>🔍 Behavioral Analysis</h2>
        <div class="quirk-grid">
    """

    for quirk in quirks[:10]:  # Limit to top 10
        significance = "✅ Significant" if quirk.get('significant', False) else "📊 Detected"
        p_value = quirk.get('p_value', 1.0)
        effect_size = quirk.get('effect_size', 0)

        quirk_html += f"""
        <div class="quirk-card">
            <h3>{quirk.get('name', 'Unknown Quirk')}</h3>
            <div class="quirk-metrics">
                <span class="metric">Impact: {quirk.get('impact', 0):.2f}</span>
                <span class="metric">p-value: {p_value:.4f}</span>
                <span class="metric">Effect: {effect_size:.2f}</span>
            </div>
            <div class="significance-badge {significance.lower()}">{significance}</div>
            <p class="quirk-description">
                Section {quirk.get('section_index', 0) + 1 if 'section_index' in quirk else 'Unknown'} causes this behavior
            </p>
        </div>
        """

    quirk_html += """
        </div>
    </div>
    """

    return quirk_html


def generate_html_report(
    evaluation_data: pd.DataFrame,
    scores: Dict[str, float],
    quirks: List[Dict[str, Any]],
    config_name: str,
    sections: List[str],
    metadata: Optional[Dict[str, Any]] = None,
    company_name: Optional[str] = None,
    company_logo: Optional[str] = None
) -> str:
    """
    Generate complete HTML report

    Args:
        evaluation_data: DataFrame with evaluation results
        scores: Dimension scores
        quirks: Detected quirks
        config_name: Configuration name
        sections: List of prompt sections
        metadata: Additional metadata
        company_name: Optional company name for branding
        company_logo: Optional base64 encoded logo

    Returns:
        Complete HTML string
    """

    # Generate report sections
    executive_summary = generate_executive_summary(scores, quirks, config_name, len(sections))
    performance_charts = create_performance_charts(evaluation_data)
    quirk_analysis = create_quirk_analysis_section(quirks)

    # Generate timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Create sections data
    sections_html = ""
    for i, section in enumerate(sections):
        sections_html += f"""
        <div class="section-card">
            <h4>Section {i+1}</h4>
            <pre>{section[:200]}...</pre>
        </div>
        """

    # Build complete HTML
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Prompt Evaluation Report - {config_name}</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                background: linear-gradient(135deg, #0f0f1e 0%, #1a1a2e 100%);
                color: #e2e8f0;
                line-height: 1.6;
            }}

            .container {{
                max-width: 1200px;
                margin: 0 auto;
                padding: 2rem;
            }}

            header {{
                text-align: center;
                padding: 3rem 0;
                border-bottom: 2px solid rgba(59, 130, 246, 0.3);
                margin-bottom: 3rem;
                background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%);
                border-radius: 1rem;
            }}

            h1 {{
                font-size: 2.5rem;
                margin-bottom: 1rem;
                background: linear-gradient(90deg, #3b82f6 0%, #8b5cf6 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}

            h2 {{
                font-size: 1.8rem;
                margin: 2rem 0 1rem;
                color: #60a5fa;
            }}

            h3 {{
                font-size: 1.3rem;
                margin: 1.5rem 0 0.5rem;
                color: #93c5fd;
            }}

            .metadata {{
                display: flex;
                justify-content: center;
                gap: 2rem;
                margin-top: 1rem;
                font-size: 0.9rem;
                color: #94a3b8;
            }}

            .executive-summary {{
                background: rgba(30, 41, 59, 0.5);
                border: 1px solid rgba(59, 130, 246, 0.3);
                border-radius: 1rem;
                padding: 2rem;
                margin-bottom: 3rem;
            }}

            .summary-card {{
                background: rgba(15, 23, 42, 0.5);
                border-radius: 0.5rem;
                padding: 1.5rem;
                margin-top: 1rem;
            }}

            .lead {{
                font-size: 1.1rem;
                margin-bottom: 1.5rem;
                color: #cbd5e1;
            }}

            .key-findings, .recommendations {{
                margin-top: 1.5rem;
            }}

            .key-findings ul, .recommendations ul {{
                list-style-position: inside;
                margin-left: 1rem;
            }}

            .key-findings li, .recommendations li {{
                margin: 0.5rem 0;
            }}

            .charts-section {{
                margin-bottom: 3rem;
            }}

            .quirks-section {{
                background: rgba(30, 41, 59, 0.5);
                border-radius: 1rem;
                padding: 2rem;
                margin-bottom: 3rem;
            }}

            .quirk-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 1rem;
                margin-top: 1.5rem;
            }}

            .quirk-card {{
                background: rgba(15, 23, 42, 0.8);
                border: 1px solid rgba(59, 130, 246, 0.2);
                border-radius: 0.5rem;
                padding: 1rem;
                transition: transform 0.2s, box-shadow 0.2s;
            }}

            .quirk-card:hover {{
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
            }}

            .quirk-metrics {{
                display: flex;
                gap: 1rem;
                margin: 0.5rem 0;
                font-size: 0.85rem;
            }}

            .metric {{
                background: rgba(59, 130, 246, 0.1);
                padding: 0.25rem 0.5rem;
                border-radius: 0.25rem;
            }}

            .significance-badge {{
                display: inline-block;
                padding: 0.25rem 0.75rem;
                border-radius: 1rem;
                font-size: 0.85rem;
                margin: 0.5rem 0;
            }}

            .significance-badge.significant {{
                background: rgba(16, 185, 129, 0.2);
                color: #10b981;
                border: 1px solid #10b981;
            }}

            .significance-badge.detected {{
                background: rgba(245, 158, 11, 0.2);
                color: #f59e0b;
                border: 1px solid #f59e0b;
            }}

            .sections-container {{
                margin-bottom: 3rem;
            }}

            .section-card {{
                background: rgba(30, 41, 59, 0.5);
                border: 1px solid rgba(59, 130, 246, 0.2);
                border-radius: 0.5rem;
                padding: 1rem;
                margin: 1rem 0;
            }}

            .section-card pre {{
                background: rgba(0, 0, 0, 0.3);
                padding: 0.5rem;
                border-radius: 0.25rem;
                overflow-x: auto;
                font-size: 0.85rem;
                margin-top: 0.5rem;
            }}

            .tabs {{
                display: flex;
                gap: 1rem;
                margin-bottom: 2rem;
                border-bottom: 2px solid rgba(59, 130, 246, 0.3);
            }}

            .tab {{
                padding: 0.75rem 1.5rem;
                background: none;
                border: none;
                color: #94a3b8;
                cursor: pointer;
                transition: all 0.3s;
                border-bottom: 2px solid transparent;
                margin-bottom: -2px;
            }}

            .tab:hover {{
                color: #60a5fa;
            }}

            .tab.active {{
                color: #3b82f6;
                border-bottom-color: #3b82f6;
            }}

            .tab-content {{
                display: none;
            }}

            .tab-content.active {{
                display: block;
            }}

            footer {{
                text-align: center;
                padding: 2rem;
                margin-top: 4rem;
                border-top: 1px solid rgba(59, 130, 246, 0.3);
                color: #64748b;
            }}

            @media print {{
                body {{
                    background: white;
                    color: black;
                }}

                .tabs {{
                    display: none;
                }}

                .tab-content {{
                    display: block !important;
                }}
            }}

            .print-button {{
                position: fixed;
                bottom: 2rem;
                right: 2rem;
                background: linear-gradient(90deg, #3b82f6 0%, #8b5cf6 100%);
                color: white;
                border: none;
                padding: 1rem 2rem;
                border-radius: 2rem;
                cursor: pointer;
                font-weight: 600;
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
                transition: all 0.3s;
            }}

            .print-button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(59, 130, 246, 0.6);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                {f'<img src="{company_logo}" alt="{company_name}" style="height: 60px; margin-bottom: 1rem;">' if company_logo else ''}
                <h1>Prompt Evaluation Report</h1>
                <div class="metadata">
                    <span>📅 Generated: {timestamp}</span>
                    <span>🔧 Configuration: {config_name}</span>
                    <span>📍 Sections: {len(sections)}</span>
                    <span>📊 Avg Score: {sum(scores.values())/len(scores) if scores else 0:.1f}%</span>
                </div>
            </header>

            <div class="tabs">
                <button class="tab active" onclick="showTab(event, 'summary')">Executive Summary</button>
                <button class="tab" onclick="showTab(event, 'performance')">Performance</button>
                <button class="tab" onclick="showTab(event, 'quirks')">Behavioral Analysis</button>
                <button class="tab" onclick="showTab(event, 'sections')">Prompt Sections</button>
            </div>

            <div id="summary" class="tab-content active">
                {executive_summary}
            </div>

            <div id="performance" class="tab-content">
                {performance_charts}
            </div>

            <div id="quirks" class="tab-content">
                {quirk_analysis}
            </div>

            <div id="sections" class="tab-content">
                <div class="sections-container">
                    <h2>📝 Prompt Sections</h2>
                    {sections_html}
                </div>
            </div>

            <footer>
                <p>Generated by Prompt Testing Tool | {company_name or 'Your Company'}</p>
                <p style="margin-top: 0.5rem; font-size: 0.85rem;">
                    This report contains proprietary evaluation data. Handle with appropriate confidentiality.
                </p>
            </footer>
        </div>

        <button class="print-button" onclick="window.print()">🖨️ Print Report</button>

        <script>
            function showTab(evt, tabName) {{
                var i, tabcontent, tabs;
                tabcontent = document.getElementsByClassName("tab-content");
                for (i = 0; i < tabcontent.length; i++) {{
                    tabcontent[i].classList.remove("active");
                }}
                tabs = document.getElementsByClassName("tab");
                for (i = 0; i < tabs.length; i++) {{
                    tabs[i].classList.remove("active");
                }}
                document.getElementById(tabName).classList.add("active");
                evt.currentTarget.classList.add("active");
            }}
        </script>
    </body>
    </html>
    """

    return html


def save_report(
    html_content: str,
    filename: str = "prompt_evaluation_report.html"
) -> str:
    """
    Save HTML report to file

    Args:
        html_content: HTML string
        filename: Output filename

    Returns:
        Path to saved file
    """
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return filename