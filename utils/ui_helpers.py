"""
UI Helper functions for Streamlit app - keeps main app clean
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Tuple, Optional

from config import (
    EVALUATION_DIMENSIONS, DIMENSION_KEYWORDS,
    COLOR_PRIMARY, COLOR_SECONDARY
)


def extract_dimension_scores(df: pd.DataFrame) -> Dict[str, float]:
    """
    Extract and calculate dimension scores from evaluation data

    Args:
        df: DataFrame with evaluation results

    Returns:
        Dictionary mapping dimension names to average scores
    """
    # Collect scores for each dimension
    dimension_scores = {dim: [] for dim in EVALUATION_DIMENSIONS}

    for _, row in df.iterrows():
        question = row['evaluation_question']
        score = row['evaluation_score']

        # Skip failed evaluations
        if pd.isna(score) or score is None or score == '':
            continue

        try:
            score = float(score)
        except (ValueError, TypeError):
            continue

        # Match question to dimension using keywords
        question_upper = question.upper()
        for dimension, keywords in DIMENSION_KEYWORDS.items():
            if any(keyword in question_upper for keyword in keywords):
                dimension_scores[dimension].append(score)
                break  # Stop after first match

    # Calculate averages
    avg_scores = {}
    for dim in EVALUATION_DIMENSIONS:
        if dimension_scores[dim]:
            avg_scores[dim] = sum(dimension_scores[dim]) / len(dimension_scores[dim])
        else:
            avg_scores[dim] = 0

    return avg_scores


def create_radar_chart(avg_scores: Dict[str, float], full_avg_scores: Optional[Dict[str, float]] = None, baseline_label: Optional[str] = None) -> go.Figure:
    """
    Create enhanced radar chart

    Args:
        avg_scores: Dictionary of dimension scores for current selection
        full_avg_scores: Optional dictionary of scores for full prompt comparison
        baseline_label: Optional label for the baseline configuration

    Returns:
        Plotly Figure object
    """
    fig = go.Figure()

    # Extract categories and values from the dictionary
    categories = list(avg_scores.keys())
    values = list(avg_scores.values())

    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]],
        theta=categories + [categories[0]],
        fill='toself',
        name='Current Selection',
        line=dict(color=COLOR_PRIMARY, width=3),
        fillcolor=f'rgba(59, 130, 246, 0.25)',
        marker=dict(size=8, color=COLOR_PRIMARY)
    ))

    if full_avg_scores is not None:
        full_values = [full_avg_scores.get(cat, 0) for cat in categories]
        baseline_name = f"Full Prompt ({baseline_label})" if baseline_label else "Full System Prompt"
        fig.add_trace(go.Scatterpolar(
            r=full_values + [full_values[0]],
            theta=categories + [categories[0]],
            fill='toself',
            name=baseline_name,
            line=dict(color=COLOR_SECONDARY, width=2.5),
            fillcolor=f'rgba(239, 68, 68, 0.15)',
            opacity=0.85,
            marker=dict(size=6, color=COLOR_SECONDARY)
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], showticklabels=False,
                          tickmode='linear', tick0=0, dtick=20, gridcolor='rgba(128, 128, 128, 0.2)'),
            angularaxis=dict(visible=True, showticklabels=True, tickfont=dict(color='#d4d4d8', size=11)),
            bgcolor='rgba(0,0,0,0)'
        ),
        showlegend=True,
        legend=dict(x=0.02, y=0.98, bgcolor='rgba(39, 39, 42, 0.8)',
                   bordercolor='rgba(63, 63, 70, 0.5)', borderwidth=1, font=dict(color='#d4d4d8', size=11)),
        height=400, margin=dict(l=40, r=40, t=20, b=40),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig


def create_bar_chart(avg_scores: Dict[str, float], full_avg_scores: Optional[Dict[str, float]] = None, baseline_label: Optional[str] = None) -> go.Figure:
    """
    Create enhanced bar chart

    Args:
        avg_scores: Dictionary of dimension scores for current selection
        full_avg_scores: Optional dictionary of scores for full prompt comparison
        baseline_label: Optional label for the baseline configuration

    Returns:
        Plotly Figure object
    """
    fig = go.Figure()

    # Extract categories and values from the dictionary
    categories = list(avg_scores.keys())
    values = list(avg_scores.values())

    fig.add_trace(go.Bar(
        x=categories, y=values, name='Current Selection',
        marker=dict(color=COLOR_PRIMARY, line=dict(color='rgb(37, 99, 235)', width=1.5), cornerradius=4),
        opacity=0.9
    ))

    if full_avg_scores is not None:
        full_values = [full_avg_scores.get(cat, 0) for cat in categories]
        baseline_name = f"Full Prompt ({baseline_label})" if baseline_label else "Full System Prompt"
        fig.add_trace(go.Bar(
            x=categories, y=full_values, name=baseline_name,
            marker=dict(color=COLOR_SECONDARY, line=dict(color='rgb(220, 38, 38)', width=1.5), cornerradius=4),
            opacity=0.85
        ))

    fig.update_layout(
        barmode='group',
        yaxis=dict(range=[0, 100], title=dict(text='Score', font=dict(color='#d4d4d8', size=12, family='Inter')),
                  gridcolor='rgba(39, 39, 42, 0.5)', tickfont=dict(color='#a1a1aa', size=11)),
        xaxis=dict(title=dict(text='Dimensions', font=dict(color='#d4d4d8', size=12, family='Inter')),
                  tickfont=dict(color='#a1a1aa', size=11)),
        legend=dict(bgcolor='rgba(39, 39, 42, 0.8)', bordercolor='rgba(63, 63, 70, 0.5)',
                   borderwidth=1, font=dict(color='#d4d4d8', size=11)),
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        height=300, margin=dict(l=50, r=20, t=10, b=40)
    )
    return fig


def create_response_metrics_charts(df: pd.DataFrame, full_df: pd.DataFrame = None) -> Tuple[go.Figure, go.Figure]:
    """
    Create charts for response characteristics (word count, readability)

    Args:
        df: DataFrame with evaluation results for current selection
        full_df: Optional DataFrame with full dataset for comparison

    Returns:
        Tuple of (word_count_chart, readability_chart)
    """
    # Filter successful evaluations
    success_df = df[df['success'] == True].copy()

    # Check if metrics columns exist (for backward compatibility)
    has_metrics = all(col in df.columns for col in ['word_count', 'readability_score', 'grade_level'])

    if success_df.empty or not has_metrics:
        # Return empty charts
        empty_fig = go.Figure()
        empty_fig.update_layout(
            title="Metrics not available (run new evaluation to see response characteristics)",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#d4d4d8'),
            height=200
        )
        return empty_fig, empty_fig

    # Calculate global maximum from full dataset if provided, otherwise use current data
    if full_df is not None and not full_df.empty:
        full_success_df = full_df[full_df['success'] == True].copy()
        if not full_success_df.empty and 'word_count' in full_success_df.columns:
            all_metrics = full_success_df.groupby('system_prompt')['word_count'].mean()
            global_max_word_count = all_metrics.max()
        else:
            global_max_word_count = success_df['word_count'].max() if not success_df.empty else 400
    else:
        global_max_word_count = success_df['word_count'].max() if not success_df.empty else 400

    y_max = global_max_word_count * 1.1  # Add 10% padding above the highest bar globally

    # Then group the filtered data for display
    metrics_by_prompt = success_df.groupby('system_prompt').agg({
        'word_count': 'mean',
        'readability_score': 'mean',
        'grade_level': 'mean'
    }).reset_index()

    # Word Count Chart
    word_fig = px.bar(
        metrics_by_prompt,
        x=[1] * len(metrics_by_prompt),  # Single bar, no labels needed
        y='word_count',
        title="Average Word Count"
    )

    word_fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#d4d4d8', family='Inter'),
        title=dict(font=dict(color='#d4d4d8', size=14)),
        xaxis=dict(title="", color='#d4d4d8', showticklabels=False),
        yaxis=dict(
            title="Average Words",
            color='#d4d4d8',
            range=[0, y_max]  # Dynamic scale: 0 to max_word_count + 10%
        ),
        height=250,
        showlegend=False
    )

    # Make all bars the same color
    word_fig.update_traces(marker_color=COLOR_PRIMARY)

    # Readability Chart
    readability_fig = px.scatter(
        metrics_by_prompt,
        x='readability_score',
        y='grade_level',
        size='word_count',
        title="Readability: Flesch Score vs Grade Level",
        labels={
            'readability_score': 'Flesch Reading Ease (higher = easier)',
            'grade_level': 'Grade Level Required'
        }
    )

    readability_fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#d4d4d8', family='Inter'),
        title=dict(font=dict(color='#d4d4d8', size=14)),
        xaxis=dict(color='#d4d4d8'),
        yaxis=dict(color='#d4d4d8'),
        height=300  # Match the bar chart height
    )

    return word_fig, readability_fig


def extract_response_metrics_summary(df: pd.DataFrame) -> Dict[str, float]:
    """
    Extract summary statistics for response metrics

    Args:
        df: DataFrame with evaluation results

    Returns:
        Dictionary with average metrics across all responses
    """
    success_df = df[df['success'] == True]

    # Check if metrics columns exist (for backward compatibility)
    has_metrics = all(col in df.columns for col in ['word_count', 'readability_score', 'grade_level'])

    if success_df.empty or not has_metrics:
        return {
            'avg_word_count': 0,
            'avg_readability': 0,
            'avg_grade_level': 0
        }

    return {
        'avg_word_count': round(success_df['word_count'].mean(), 1),
        'avg_readability': round(success_df['readability_score'].mean(), 1),
        'avg_grade_level': round(success_df['grade_level'].mean(), 1)
    }


def extract_question_asking_metrics(df: pd.DataFrame) -> Dict[str, any]:
    """
    Extract question-asking behavior metrics from evaluation results

    Args:
        df: DataFrame with evaluation results

    Returns:
        Dictionary with question-asking metrics:
        - avg_question_asking_score: Average score (0-100)
        - asks_percentage: Percentage of responses that ask questions
        - assumes_percentage: Percentage that make assumptions
        - neutral_percentage: Percentage that are neutral
        - avg_question_marks: Average question marks per response
        - avg_clarification_phrases: Average clarification phrases
    """
    success_df = df[df['success'] == True]

    # Check if question-asking columns exist (for backward compatibility)
    qa_columns = ['question_asking_score', 'asks_vs_assumes', 'question_marks', 'clarification_phrases']
    has_qa_metrics = all(col in df.columns for col in qa_columns)

    if success_df.empty or not has_qa_metrics:
        return {
            'avg_question_asking_score': 0,
            'asks_percentage': 0,
            'assumes_percentage': 0,
            'neutral_percentage': 0,
            'avg_question_marks': 0,
            'avg_clarification_phrases': 0
        }

    # Calculate percentages
    asks_count = len(success_df[success_df['asks_vs_assumes'] == 'asks'])
    assumes_count = len(success_df[success_df['asks_vs_assumes'] == 'assumes'])
    neutral_count = len(success_df[success_df['asks_vs_assumes'] == 'neutral'])
    total = len(success_df)

    return {
        'avg_question_asking_score': round(success_df['question_asking_score'].mean(), 1),
        'asks_percentage': round((asks_count / total) * 100, 1) if total > 0 else 0,
        'assumes_percentage': round((assumes_count / total) * 100, 1) if total > 0 else 0,
        'neutral_percentage': round((neutral_count / total) * 100, 1) if total > 0 else 0,
        'avg_question_marks': round(success_df['question_marks'].mean(), 2),
        'avg_clarification_phrases': round(success_df['clarification_phrases'].mean(), 2)
    }


def create_question_asking_chart(df: pd.DataFrame, full_df: pd.DataFrame = None) -> go.Figure:
    """
    Create chart showing question-asking behavior across prompts

    Args:
        df: DataFrame with evaluation results for current selection
        full_df: Optional DataFrame with full dataset for comparison

    Returns:
        Plotly Figure object
    """
    from config import COLOR_PRIMARY, COLOR_SECONDARY

    # Filter successful evaluations
    success_df = df[df['success'] == True].copy()

    # Check if metrics columns exist
    has_metrics = 'asks_vs_assumes' in df.columns

    if success_df.empty or not has_metrics:
        # Return empty chart
        empty_fig = go.Figure()
        empty_fig.update_layout(
            title="Question-Asking Behavior (run new evaluation to see this metric)",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#d4d4d8'),
            height=300
        )
        return empty_fig

    # Group by system prompt and calculate percentages
    metrics_by_prompt = success_df.groupby('system_prompt').agg({
        'asks_vs_assumes': lambda x: (x == 'asks').sum() / len(x) * 100
    }).reset_index()
    metrics_by_prompt.columns = ['system_prompt', 'asks_percentage']

    # Create bar chart
    fig = px.bar(
        metrics_by_prompt,
        x=[1] * len(metrics_by_prompt),  # Single bar
        y='asks_percentage',
        title="Question-Asking Behavior"
    )

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#d4d4d8', family='Inter'),
        title=dict(font=dict(color='#d4d4d8', size=14)),
        xaxis=dict(title="", color='#d4d4d8', showticklabels=False),
        yaxis=dict(
            title="% of Responses That Ask Questions",
            color='#d4d4d8',
            range=[0, 100]
        ),
        height=250,
        showlegend=False
    )

    fig.update_traces(marker_color=COLOR_PRIMARY)

    return fig


def calculate_section_impact(df: pd.DataFrame, sections: list) -> pd.DataFrame:
    """
    Calculate the impact of each section on each metric dimension

    Uses section metadata when available (section_names column), otherwise falls back
    to string matching for backward compatibility.

    Args:
        df: DataFrame with evaluation results
        sections: List of section strings

    Returns:
        DataFrame with sections as rows and dimensions as columns, values are impact scores
    """
    impact_data = []

    # Check if we have section metadata
    has_metadata = 'section_names' in df.columns and df['section_names'].notna().any()

    for i, section in enumerate(sections):
        section_impacts = {'section': section[:50] + '...' if len(section) > 50 else section}  # Truncate long sections

        if has_metadata:
            # Use metadata-based approach (more accurate)
            # Find rows where this section name appears in the section_names column
            # section_names is comma-separated, so we check if section string matches any part
            # Since we don't have the section name explicitly, we need to use string matching still
            # This is a limitation - we'd need to pass section names separately for full metadata usage
            prompts_with_section = df[df['system_prompt'].str.contains(section, regex=False)]['system_prompt'].unique()
            prompts_without_section = df[~df['system_prompt'].str.contains(section, regex=False)]['system_prompt'].unique()
        else:
            # Fallback to string matching (legacy approach)
            prompts_with_section = df[df['system_prompt'].str.contains(section, regex=False)]['system_prompt'].unique()
            prompts_without_section = df[~df['system_prompt'].str.contains(section, regex=False)]['system_prompt'].unique()

        # Skip if we don't have data for both conditions
        if len(prompts_with_section) == 0 or len(prompts_without_section) == 0:
            # If section is always present or always absent, impact is 0
            for dim in EVALUATION_DIMENSIONS:
                section_impacts[dim] = 0
            impact_data.append(section_impacts)
            continue

        # Calculate average scores with and without this section
        with_section_df = df[df['system_prompt'].isin(prompts_with_section)]
        without_section_df = df[df['system_prompt'].isin(prompts_without_section)]

        with_scores = extract_dimension_scores(with_section_df)
        without_scores = extract_dimension_scores(without_section_df)

        # Calculate impact (difference)
        for dim in EVALUATION_DIMENSIONS:
            with_score = with_scores.get(dim, 0)
            without_score = without_scores.get(dim, 0)

            # Only calculate impact if we have valid scores for both
            if with_score > 0 and without_score > 0:
                section_impacts[dim] = with_score - without_score
            else:
                section_impacts[dim] = 0

        impact_data.append(section_impacts)

    return pd.DataFrame(impact_data)


def create_section_impact_heatmap(df: pd.DataFrame, sections: list) -> go.Figure:
    """
    Create heatmap showing which sections affect which metrics

    Args:
        df: DataFrame with evaluation results
        sections: List of section strings

    Returns:
        Plotly Figure object
    """
    # Calculate section impacts
    impact_df = calculate_section_impact(df, sections)

    if impact_df.empty:
        empty_fig = go.Figure()
        empty_fig.update_layout(
            title="Section Impact Heatmap (not enough data)",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#d4d4d8'),
            height=300
        )
        return empty_fig

    # Prepare data for heatmap
    section_labels = impact_df['section'].tolist()
    dimensions = EVALUATION_DIMENSIONS

    # Create matrix of impact values
    impact_matrix = []
    for _, row in impact_df.iterrows():
        impact_row = [row[dim] for dim in dimensions]
        impact_matrix.append(impact_row)

    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=impact_matrix,
        x=dimensions,
        y=section_labels,
        colorscale=[
            [0.0, '#ef4444'],  # Red for negative impact
            [0.5, '#18181b'],  # Dark gray for zero
            [1.0, '#22c55e']   # Green for positive impact
        ],
        zmid=0,  # Center colorscale at 0
        text=[[f"{val:+.1f}" for val in row] for row in impact_matrix],
        texttemplate='%{text}',
        textfont={"size": 10, "color": "#fafafa"},
        colorbar=dict(
            title="Impact",
            titleside="right",
            tickmode="linear",
            tick0=-20,
            dtick=10,
            tickfont=dict(color='#d4d4d8'),
            titlefont=dict(color='#d4d4d8')
        )
    ))

    fig.update_layout(
        title="Section Impact on Metrics (vs prompts without each section)",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#d4d4d8', family='Inter'),
        xaxis=dict(
            title="Metric Dimensions",
            tickfont=dict(color='#d4d4d8', size=11),
            titlefont=dict(color='#d4d4d8')
        ),
        yaxis=dict(
            title="Prompt Sections",
            tickfont=dict(color='#d4d4d8', size=10),
            titlefont=dict(color='#d4d4d8')
        ),
        height=max(300, len(sections) * 60),  # Dynamic height based on number of sections
        margin=dict(l=200, r=100, t=60, b=60)
    )

    return fig
