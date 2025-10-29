"""
Animated Prompt Surgery Tool
Interactive drag-and-drop interface for reordering and editing prompt sections
with live preview and impact predictions
"""

import streamlit as st
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime
import json


def create_section_card(
    section: str,
    index: int,
    scores: Optional[Dict[str, float]] = None,
    impact: Optional[Dict[str, float]] = None
) -> str:
    """
    Create HTML for a draggable section card

    Args:
        section: Section text
        index: Section index
        scores: Optional scores for this section
        impact: Optional impact metrics

    Returns:
        HTML string for the card
    """
    # Calculate color based on impact
    if impact and 'overall' in impact:
        impact_value = impact['overall']
        if impact_value > 10:
            color = "#10b981"  # Green for positive
            icon = "↗️"
        elif impact_value < -10:
            color = "#ef4444"  # Red for negative
            icon = "↘️"
        else:
            color = "#6b7280"  # Gray for neutral
            icon = "→"
    else:
        color = "#3b82f6"  # Blue default
        icon = "📝"

    # Truncate section text for preview
    preview = section[:100] + "..." if len(section) > 100 else section

    return f"""
    <div class="section-card" data-index="{index}" draggable="true"
         style="background: linear-gradient(135deg, {color}22 0%, {color}11 100%);
                border-left: 4px solid {color};
                padding: 15px;
                margin: 10px 0;
                border-radius: 8px;
                cursor: move;
                transition: all 0.3s ease;
                position: relative;">
        <div style="display: flex; justify-content: space-between; align-items: start;">
            <div style="flex: 1;">
                <div style="font-weight: 600; color: {color}; margin-bottom: 8px;">
                    {icon} Section {index + 1}
                </div>
                <div style="color: #94a3b8; font-size: 0.9em; line-height: 1.4;">
                    {preview}
                </div>
                {f'<div style="margin-top: 10px; font-size: 0.85em; color: #64748b;">Impact: {impact_value:+.1f}%</div>' if impact else ''}
            </div>
            <div style="display: flex; gap: 8px;">
                <button class="edit-btn" data-index="{index}"
                        style="background: transparent; border: 1px solid {color};
                               color: {color}; padding: 4px 8px; border-radius: 4px;
                               cursor: pointer; font-size: 0.85em;">
                    Edit
                </button>
                <button class="delete-btn" data-index="{index}"
                        style="background: transparent; border: 1px solid #ef4444;
                               color: #ef4444; padding: 4px 8px; border-radius: 4px;
                               cursor: pointer; font-size: 0.85em;">
                    Delete
                </button>
            </div>
        </div>
    </div>
    """


def create_surgery_interface() -> str:
    """
    Create the HTML/JavaScript for the drag-and-drop interface

    Returns:
        HTML string with embedded JavaScript
    """
    return """
    <style>
        .surgery-container {
            min-height: 400px;
            padding: 20px;
            background: rgba(15, 23, 42, 0.5);
            border-radius: 12px;
            border: 1px solid rgba(148, 163, 184, 0.1);
        }

        .section-card {
            animation: slideIn 0.3s ease;
        }

        .section-card:hover {
            transform: translateX(5px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }

        .section-card.dragging {
            opacity: 0.5;
            transform: scale(0.95);
        }

        .section-card.drag-over {
            border-top: 3px solid #3b82f6;
            padding-top: 25px;
        }

        .add-section-btn {
            width: 100%;
            padding: 15px;
            margin-top: 20px;
            background: linear-gradient(90deg, #3b82f6 0%, #8b5cf6 100%);
            border: none;
            color: white;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s ease;
        }

        .add-section-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 16px rgba(59, 130, 246, 0.3);
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(-10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }

        .impact-preview {
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(15, 23, 42, 0.95);
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 8px;
            padding: 15px;
            max-width: 250px;
            z-index: 1000;
            animation: slideIn 0.3s ease;
        }

        .impact-metric {
            display: flex;
            justify-content: space-between;
            margin: 8px 0;
            font-size: 0.9em;
        }

        .impact-positive { color: #10b981; }
        .impact-negative { color: #ef4444; }
        .impact-neutral { color: #6b7280; }
    </style>

    <script>
        let draggedElement = null;
        let sections = [];

        function initDragAndDrop() {
            const container = document.querySelector('.surgery-container');

            container.addEventListener('dragstart', (e) => {
                if (e.target.classList.contains('section-card')) {
                    draggedElement = e.target;
                    e.target.classList.add('dragging');
                    e.dataTransfer.effectAllowed = 'move';
                }
            });

            container.addEventListener('dragover', (e) => {
                e.preventDefault();
                const afterElement = getDragAfterElement(container, e.clientY);
                const dragging = document.querySelector('.dragging');

                // Remove all drag-over classes
                document.querySelectorAll('.drag-over').forEach(el => {
                    el.classList.remove('drag-over');
                });

                if (afterElement == null) {
                    container.appendChild(dragging);
                } else {
                    afterElement.classList.add('drag-over');
                    container.insertBefore(dragging, afterElement);
                }
            });

            container.addEventListener('dragend', (e) => {
                if (e.target.classList.contains('section-card')) {
                    e.target.classList.remove('dragging');
                    document.querySelectorAll('.drag-over').forEach(el => {
                        el.classList.remove('drag-over');
                    });
                    updateSectionOrder();
                    showImpactPreview();
                }
            });

            // Edit and Delete buttons
            container.addEventListener('click', (e) => {
                if (e.target.classList.contains('edit-btn')) {
                    const index = e.target.dataset.index;
                    editSection(index);
                } else if (e.target.classList.contains('delete-btn')) {
                    const index = e.target.dataset.index;
                    deleteSection(index);
                }
            });
        }

        function getDragAfterElement(container, y) {
            const draggableElements = [...container.querySelectorAll('.section-card:not(.dragging)')];

            return draggableElements.reduce((closest, child) => {
                const box = child.getBoundingClientRect();
                const offset = y - box.top - box.height / 2;

                if (offset < 0 && offset > closest.offset) {
                    return { offset: offset, element: child };
                } else {
                    return closest;
                }
            }, { offset: Number.NEGATIVE_INFINITY }).element;
        }

        function updateSectionOrder() {
            const cards = document.querySelectorAll('.section-card');
            const newOrder = [];
            cards.forEach((card, index) => {
                const originalIndex = parseInt(card.dataset.index);
                newOrder.push(originalIndex);
                // Update visual index
                card.querySelector('div > div > div').innerText = `📝 Section ${index + 1}`;
            });

            // Send to Streamlit
            window.parent.postMessage({
                type: 'section_order_changed',
                order: newOrder
            }, '*');
        }

        function editSection(index) {
            window.parent.postMessage({
                type: 'edit_section',
                index: parseInt(index)
            }, '*');
        }

        function deleteSection(index) {
            if (confirm('Delete this section?')) {
                window.parent.postMessage({
                    type: 'delete_section',
                    index: parseInt(index)
                }, '*');
            }
        }

        function showImpactPreview() {
            // Simulate impact calculation
            const preview = document.createElement('div');
            preview.className = 'impact-preview';
            preview.innerHTML = `
                <h4 style="margin: 0 0 10px 0; color: #3b82f6;">Predicted Impact</h4>
                <div class="impact-metric">
                    <span>Helpfulness</span>
                    <span class="impact-positive">+5.2%</span>
                </div>
                <div class="impact-metric">
                    <span>Directness</span>
                    <span class="impact-negative">-2.1%</span>
                </div>
                <div class="impact-metric">
                    <span>Critical Thinking</span>
                    <span class="impact-positive">+8.3%</span>
                </div>
                <div class="impact-metric">
                    <span>Overall</span>
                    <span class="impact-positive">+3.8%</span>
                </div>
            `;

            // Remove existing preview
            const existing = document.querySelector('.impact-preview');
            if (existing) existing.remove();

            document.body.appendChild(preview);

            // Auto-hide after 3 seconds
            setTimeout(() => {
                preview.style.animation = 'slideIn 0.3s ease reverse';
                setTimeout(() => preview.remove(), 300);
            }, 3000);
        }

        // Initialize on load
        document.addEventListener('DOMContentLoaded', initDragAndDrop);
    </script>
    """


def predict_section_impact(
    sections: List[str],
    historical_data: Optional[pd.DataFrame] = None
) -> Dict[str, float]:
    """
    Predict the impact of the current section configuration

    Args:
        sections: List of section texts
        historical_data: Optional historical evaluation data

    Returns:
        Dictionary of predicted impacts by dimension
    """
    # Simulate impact prediction (would use ML model in production)
    np.random.seed(len(''.join(sections)))  # Deterministic based on content

    impacts = {
        'Helpfulness': np.random.uniform(-10, 15),
        'Directness': np.random.uniform(-5, 10),
        'Critical Thinking': np.random.uniform(-8, 20),
        'Accuracy': np.random.uniform(-3, 8),
        'Tone Appropriateness': np.random.uniform(-5, 5),
        'Safety & Ethics': np.random.uniform(-2, 10)
    }

    # Calculate overall impact
    impacts['overall'] = np.mean(list(impacts.values()))

    return impacts


def create_live_preview(
    sections: List[str],
    preview_query: str = "How do I implement a binary search tree?"
) -> str:
    """
    Create a live preview showing how the prompt would respond

    Args:
        sections: Current section configuration
        preview_query: Sample query to preview

    Returns:
        HTML string with preview
    """
    # Construct the full prompt
    full_prompt = "\n\n".join(sections)

    # Simulate response characteristics based on sections
    characteristics = []

    if any("direct" in s.lower() for s in sections):
        characteristics.append("• Response will be more concise")
    if any("example" in s.lower() for s in sections):
        characteristics.append("• Will include code examples")
    if any("critical" in s.lower() or "think" in s.lower() for s in sections):
        characteristics.append("• Will analyze multiple approaches")
    if any("uncertain" in s.lower() for s in sections):
        characteristics.append("• Will express appropriate uncertainty")

    return f"""
    <div style="background: rgba(59, 130, 246, 0.1);
                border: 1px solid rgba(59, 130, 246, 0.3);
                border-radius: 8px;
                padding: 15px;
                margin-top: 20px;">
        <h4 style="margin: 0 0 10px 0; color: #3b82f6;">
            Live Preview: "{preview_query}"
        </h4>
        <div style="font-size: 0.9em; color: #94a3b8; line-height: 1.5;">
            <p><strong>Expected Response Characteristics:</strong></p>
            {"<br>".join(characteristics) if characteristics else "• Standard response pattern"}
        </div>
        <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(148, 163, 184, 0.2);">
            <strong>Active Sections:</strong> {len(sections)}<br>
            <strong>Total Length:</strong> {len(full_prompt)} characters
        </div>
    </div>
    """


def render_prompt_surgery(
    sections: List[str],
    evaluation_data: Optional[pd.DataFrame] = None
) -> Tuple[List[str], bool]:
    """
    Render the prompt surgery interface in Streamlit

    Args:
        sections: Current list of sections
        evaluation_data: Optional historical data for predictions

    Returns:
        Tuple of (updated_sections, changed)
    """
    st.markdown("### 🔬 Prompt Surgery")
    st.markdown("Drag and drop sections to reorder, edit inline, or delete unwanted sections.")

    # Create container for sections
    surgery_html = create_surgery_interface()
    sections_html = '<div class="surgery-container">'

    for i, section in enumerate(sections):
        impact = predict_section_impact([section], evaluation_data)
        sections_html += create_section_card(section, i, impact=impact)

    sections_html += '''
        <button class="add-section-btn" onclick="window.parent.postMessage({type: 'add_section'}, '*');">
            + Add New Section
        </button>
    </div>
    '''

    # Render the interface
    st.components.v1.html(
        surgery_html + sections_html,
        height=600,
        scrolling=True
    )

    # Handle section editing
    col1, col2 = st.columns([3, 1])

    with col1:
        if st.session_state.get('edit_section_index') is not None:
            idx = st.session_state.edit_section_index
            edited_text = st.text_area(
                f"Edit Section {idx + 1}",
                value=sections[idx],
                height=100,
                key=f"edit_section_{idx}"
            )

            if st.button("Save Changes", type="primary"):
                sections[idx] = edited_text
                st.session_state.edit_section_index = None
                st.rerun()

            if st.button("Cancel"):
                st.session_state.edit_section_index = None
                st.rerun()

    with col2:
        st.markdown("#### Quick Actions")

        if st.button("🔄 Reset Order"):
            st.session_state.section_order = list(range(len(sections)))
            st.rerun()

        if st.button("📋 Copy Configuration"):
            config = json.dumps(sections, indent=2)
            st.code(config, language="json")

        if st.button("💾 Export Sections"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"prompt_sections_{timestamp}.json"
            st.download_button(
                "Download JSON",
                data=json.dumps({"sections": sections}, indent=2),
                file_name=filename,
                mime="application/json"
            )

    # Live preview
    st.markdown("### 👁️ Live Preview")
    preview_query = st.text_input(
        "Preview Query",
        value="How do I implement a binary search tree?",
        help="Enter a query to see how the prompt would respond"
    )

    preview_html = create_live_preview(sections, preview_query)
    st.markdown(preview_html, unsafe_allow_html=True)

    # Return updated sections and change flag
    return sections, False


def compare_configurations(
    config_a: List[str],
    config_b: List[str],
    evaluation_data: Optional[pd.DataFrame] = None
) -> str:
    """
    Create a visual comparison between two configurations

    Args:
        config_a: First configuration
        config_b: Second configuration
        evaluation_data: Optional evaluation data

    Returns:
        HTML string with comparison
    """
    impact_a = predict_section_impact(config_a, evaluation_data)
    impact_b = predict_section_impact(config_b, evaluation_data)

    comparison_html = """
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px;">
        <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3);
                    border-radius: 8px; padding: 15px;">
            <h4 style="color: #10b981; margin: 0 0 10px 0;">Configuration A</h4>
            <div style="font-size: 0.9em;">
                <strong>Sections:</strong> {len_a}<br>
                <strong>Overall Impact:</strong> <span style="color: {color_a}">{impact_a:.1f}%</span>
            </div>
        </div>
        <div style="background: rgba(139, 92, 246, 0.1); border: 1px solid rgba(139, 92, 246, 0.3);
                    border-radius: 8px; padding: 15px;">
            <h4 style="color: #8b5cf6; margin: 0 0 10px 0;">Configuration B</h4>
            <div style="font-size: 0.9em;">
                <strong>Sections:</strong> {len_b}<br>
                <strong>Overall Impact:</strong> <span style="color: {color_b}">{impact_b:.1f}%</span>
            </div>
        </div>
    </div>
    """.format(
        len_a=len(config_a),
        len_b=len(config_b),
        impact_a=impact_a['overall'],
        impact_b=impact_b['overall'],
        color_a="#10b981" if impact_a['overall'] > 0 else "#ef4444",
        color_b="#10b981" if impact_b['overall'] > 0 else "#ef4444"
    )

    return comparison_html