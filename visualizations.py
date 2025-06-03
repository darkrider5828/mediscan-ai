# --- START OF FILE visualizations.py ---
# (Flask-adapted version using Plotly - v1.7 - Simplified to Pie and Bar charts)

import os
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
import io
import base64
import traceback
from typing import Optional, Tuple, List, Dict, Any

# Use Agg backend for Matplotlib just in case it's imported elsewhere
import matplotlib
matplotlib.use('Agg')

# Try importing clean_csv from utils, handle potential ImportError
try:
    from utils import clean_csv
except ImportError:
    print("CRITICAL ERROR: Could not import clean_csv from utils. Ensure utils.py is accessible.")
    def clean_csv(file_path):
        print(f"Error: clean_csv function not available. Cannot clean {file_path}")
        return pd.DataFrame()

# --- Configuration Constants ---
POTENTIAL_STATUS_COLS = ['Note', 'Status', 'Interpretation', 'Risk Level', 'Condition']
STATUS_COLORS = {
    "Normal": "#28a745",
    "Borderline": "#ffc107",
    "Concerning": "#dc3545",
    "N/A": "#adb5bd",
    "Unknown": "#6c757d"
}
DEFAULT_COLOR = "#6c757d"
TEXT_COLOR_DARK = "#1F1F1F" # Use a dark color for plot text
AXIS_LINE_COLOR = "#444444" # Dark grey for axis lines/ticks
PLOTLY_TEMPLATE = "plotly_white" # Start with white bg elements

# --- Helper Functions ---
def standardize_status(note_value: Optional[Any]) -> str:
    """Standardizes status text values - Refined Logic."""
    if pd.isna(note_value): return "Unknown"
    try:
        note_str = str(note_value).strip().lower()
        note_str = ' '.join(note_str.split()) # Normalize whitespace
    except Exception: return "Unknown"
    if not note_str: return "Unknown"

    if note_str == "normal": return "Normal"
    if note_str == "borderline": return "Borderline"
    if note_str == "concerning": return "Concerning"
    if note_str == "n/a" or note_str == "nan": return "N/A"
    if "concern" in note_str: return "Concerning"
    if "border" in note_str or "equivocal" in note_str: return "Borderline"
    if "normal" in note_str or "within normal limits" in note_str : return "Normal"

    print(f"Warning: Unmapped status value encountered: '{note_value}' -> Unknown")
    return "Unknown"

def find_status_column(df_columns: List[str]) -> Optional[str]:
    """Finds the best column for status visualization, prioritizing text."""
    print(f"Searching for status column in: {df_columns}")
    preferred_text_cols = ['Note', 'Status', 'Interpretation']
    other_potential_cols = ['Risk Level', 'Condition'] # Fallback

    # Exact match preferred
    for col in df_columns:
        if col in preferred_text_cols: print(f"Viz: Using preferred column: '{col}'"); return col
    for col in df_columns:
        if col in other_potential_cols: print(f"Viz: Using fallback column: '{col}'"); return col
    # Case-insensitive preferred
    df_columns_lower = [c.lower() for c in df_columns]
    for pcol in preferred_text_cols:
        if pcol.lower() in df_columns_lower:
            idx = df_columns_lower.index(pcol.lower()); original = df_columns[idx]
            print(f"Viz: Using preferred (insensitive): '{original}'"); return original
    # Case-insensitive fallback
    for pcol in other_potential_cols:
         if pcol.lower() in df_columns_lower:
            idx = df_columns_lower.index(pcol.lower()); original = df_columns[idx]
            print(f"Viz: Using fallback (insensitive): '{original}'"); return original

    print(f"Error: No suitable status column found in {df_columns}")
    return None

def create_status_charts_plotly(df: pd.DataFrame) -> Tuple[Optional[go.Figure], Optional[go.Figure]]:
    """Creates improved Plotly donut and bar charts with dark text for export."""
    if not isinstance(df, pd.DataFrame) or df.empty: return None, None
    status_col = find_status_column(df.columns)
    if not status_col: return None, None

    fig_pie = None
    fig_bar = None

    try:
        if status_col not in df.columns: raise KeyError(f"Column '{status_col}' not found.")
        status_series = df[status_col].astype(str).apply(standardize_status)
        status_counts = status_series.value_counts()
        status_df = status_counts.reset_index(); status_df.columns = ['Status', 'Count']
        print(f"Viz: Status counts:\n{status_df}")
        if status_df.empty or status_df['Count'].sum() == 0: return None, None

        status_order = ["Normal", "Borderline", "Concerning", "N/A", "Unknown"]
        ordered_statuses = [s for s in status_order if s in status_df['Status'].tolist()]
        ordered_statuses += [s for s in status_df['Status'].tolist() if s not in ordered_statuses]
        color_map = {s: STATUS_COLORS.get(s, DEFAULT_COLOR) for s in ordered_statuses}
        total_count = int(status_df['Count'].sum())

        # --- Plotly Pie Chart (Donut) ---
        try:
            fig_pie = px.pie(status_df, values='Count', names='Status',
                             title="Biomarker Status Distribution",
                             color='Status', color_discrete_map=color_map,
                             category_orders={'Status': ordered_statuses},
                             hole=0.4, template=PLOTLY_TEMPLATE
                            )
            fig_pie.update_traces(
                hovertemplate="<b>%{label}</b>: %{value} (%{percent})<extra></extra>",
                textinfo='percent+label', textfont_size=11,
                textfont_color=TEXT_COLOR_DARK,
                marker=dict(line=dict(color=AXIS_LINE_COLOR, width=1)),
                insidetextorientation='auto',
                pull=[0.05 if s == "Concerning" else 0.02 if s == "Borderline" else 0 for s in ordered_statuses]
            )
            fig_pie.update_layout(
                title_font_size=16, title_x=0.5, title_font_color=TEXT_COLOR_DARK,
                legend_title_text='Status', legend_title_font_color=TEXT_COLOR_DARK,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5,
                            font=dict(color=TEXT_COLOR_DARK)),
                annotations=[dict(text=f'Total<br><b>{total_count}</b>', x=0.5, y=0.5, font_size=16, showarrow=False,
                                  font_color=TEXT_COLOR_DARK)],
                paper_bgcolor='rgba(255,255,255,1)',
                plot_bgcolor='rgba(255,255,255,1)',
                font=dict(color=TEXT_COLOR_DARK),
                margin=dict(l=10, r=10, t=60, b=70)
            )
            print("Viz: Plotly pie chart created.")
        except Exception as e: print(f"Viz Error (Pie): {e}"); traceback.print_exc(); fig_pie = None

        # --- Plotly Bar Chart ---
        try:
            fig_bar = px.bar(status_df, x='Status', y='Count',
                             title="Biomarker Status Counts",
                             color='Status', color_discrete_map=color_map,
                             category_orders={'Status': ordered_statuses},
                             text='Count', template=PLOTLY_TEMPLATE
                            )
            fig_bar.update_traces(
                hovertemplate="<b>%{x}</b>: %{y} Tests<extra></extra>",
                textposition='outside', textfont_size=11, textangle=0,
                textfont_color=TEXT_COLOR_DARK,
                marker=dict(line=dict(color=AXIS_LINE_COLOR, width=0.5))
            )
            max_y = status_df['Count'].max() if not status_df.empty else 0
            y_range_upper = max(2, max_y + max(1, max_y * 0.20))

            fig_bar.update_layout(
                title_font_size=16, title_x=0.5, title_font_color=TEXT_COLOR_DARK,
                xaxis_title=None,
                yaxis_title=dict(text="Number of Tests", font=dict(color=TEXT_COLOR_DARK)),
                xaxis=dict(categoryorder='array', categoryarray=ordered_statuses,
                           showline=True, linecolor=AXIS_LINE_COLOR,
                           ticks='outside', tickcolor=AXIS_LINE_COLOR,
                           tickfont={'color': TEXT_COLOR_DARK}),
                yaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.5)', range=[0, y_range_upper],
                           showline=True, linecolor=AXIS_LINE_COLOR,
                           ticks='outside', tickcolor=AXIS_LINE_COLOR,
                           tickfont={'color': TEXT_COLOR_DARK}),
                showlegend=False,
                paper_bgcolor='rgba(255,255,255,1)',
                plot_bgcolor='rgba(255,255,255,1)',
                font=dict(color=TEXT_COLOR_DARK, size=11),
                bargap=0.3,
                margin=dict(l=50, r=10, t=60, b=30)
            )
            fig_bar.update_yaxes(rangemode='tozero', tickformat='d')
            print("Viz: Plotly bar chart created.")
        except Exception as e: print(f"Viz Error (Bar): {e}"); traceback.print_exc(); fig_bar = None

    except KeyError as ke: print(f"Viz Error: KeyError '{status_col}': {ke}"); return None, None
    except Exception as e: print(f"Viz Error (Data Prep): {e}"); traceback.print_exc(); return None, None

    return fig_pie, fig_bar

def generate_visualizations(csv_file_path: str) -> Optional[Dict[str, str]]:
    """Loads data, generates Plotly charts, exports as base64 PNGs."""
    if not csv_file_path or not os.path.exists(csv_file_path):
        print(f"Viz Error: CSV not found '{csv_file_path}'.")
        return None

    print(f"Viz: Generating visualizations from: {csv_file_path}")
    generated_plots_base64 = {}

    try:
        df = clean_csv(csv_file_path)
        if df.empty: print("Viz: Cleaned DataFrame is empty."); return {}

        fig_pie, fig_bar = create_status_charts_plotly(df)

        # Export common function
        def export_fig(fig, title):
            if not fig: return None
            try:
                print(f"Viz: Exporting '{title}' to PNG...")
                img_bytes = pio.to_image(fig, format="png", scale=1.5)
                b64_string = base64.b64encode(img_bytes).decode('utf-8')
                print(f"Viz: '{title}' exported successfully.")
                return b64_string
            except ValueError as ve:
                 if "requires the kaleido package" in str(ve): print("\nVIZ ERROR: Kaleido package missing. `pip install -U kaleido`\n"); return "Error: Kaleido missing."
                 else: print(f"Viz Error (Export '{title}'): {ve}"); traceback.print_exc(); return None
            except Exception as e: print(f"Viz Error (Export '{title}'): {e}"); traceback.print_exc(); return None

        # Export charts if they exist
        pie_b64 = export_fig(fig_pie, "Status Distribution (Pie Chart)")
        if pie_b64: generated_plots_base64["Status Distribution (Pie Chart)"] = pie_b64

        bar_b64 = export_fig(fig_bar, "Status Counts (Bar Chart)")
        if bar_b64: generated_plots_base64["Status Counts (Bar Chart)"] = bar_b64

        # --- Histogram Section Removed ---
        # value_col_numeric = 'Value_Numeric'
        # if value_col_numeric in df.columns and df[value_col_numeric].notna().any():
        #      numeric_values = df[value_col_numeric].dropna()
        #      if not numeric_values.empty:
        #         try:
        #             print("Viz: Creating numeric value histogram...")
        #             fig_hist = px.histogram(numeric_values, title="Numerical Test Value Distribution",
        #                                     template=PLOTLY_TEMPLATE, nbins=25)
        #             fig_hist.update_layout(
        #                 title_font_size=16, title_x=0.5, title_font_color=TEXT_COLOR_DARK,
        #                 xaxis_title=dict(text="Value", font=dict(color=TEXT_COLOR_DARK)),
        #                 yaxis_title=dict(text="Frequency", font=dict(color=TEXT_COLOR_DARK)),
        #                 xaxis=dict(showline=True, linecolor=AXIS_LINE_COLOR, ticks='outside', tickcolor=AXIS_LINE_COLOR, tickfont={'color': TEXT_COLOR_DARK}),
        #                 yaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.5)', showline=True, linecolor=AXIS_LINE_COLOR, ticks='outside', tickcolor=AXIS_LINE_COLOR, tickfont={'color': TEXT_COLOR_DARK}),
        #                 paper_bgcolor='rgba(255,255,255,1)', plot_bgcolor='rgba(255,255,255,1)',
        #                 font=dict(color=TEXT_COLOR_DARK, size=11), bargap=0.1,
        #                 margin=dict(l=50, r=20, t=60, b=40)
        #             )
        #             fig_hist.update_traces(marker_color='#636EFA')
        #             hist_b64 = export_fig(fig_hist, "Numerical Value Distribution")
        #             if hist_b64: generated_plots_base64["Numerical Value Distribution"] = hist_b64
        #         except Exception as e: print(f"Viz Error (Histogram): {e}"); traceback.print_exc()
        # --- End of Histogram Section Removal ---

        print(f"Viz: Finished. Created {len(generated_plots_base64)} plots.")
        return generated_plots_base64

    except Exception as e:
        print(f"Viz Error (Main): {e}"); traceback.print_exc()
        # Return what has been generated so far, even if an error occurred later
        return generated_plots_base64
# --- END OF FILE visualizations.py ---