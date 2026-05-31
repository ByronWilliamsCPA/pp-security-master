"""
Security-Master Gradio Web Interface - Comprehensive Template

Enterprise-grade web interface for Security-Master system leveraging PromptCraft patterns.
Provides complete functionality for securities classification, data import, analytics, and
Portfolio Performance integration.

Features:
- Multi-tab interface adapted from PromptCraft journey patterns
- Role-based access control with Cloudflare Access integration
- Real-time data quality monitoring and validation
- Portfolio analytics with benchmark comparison
- Complete Portfolio Performance export generation
- Mobile-responsive design with accessibility enhancements
"""

import logging
from datetime import date, timedelta

import gradio as gr
import pandas as pd
import plotly.graph_objects as go

# PromptCraft integration imports (adapt as available)
try:
    from src.ui.components.accessibility_enhancements import create_accessible_interface
    from src.ui.components.shared.export_utils import ExportUtils

    PROMPTCRAFT_AVAILABLE = True
except ImportError:
    PROMPTCRAFT_AVAILABLE = False
    print("⚠️  PromptCraft components not available, using fallback implementations")

# Security-Master imports
from src.security_master.analytics.benchmark_generator import BenchmarkSecurityGenerator
from src.security_master.classifier.core import SecurityClassifier
from src.security_master.extractor.altoira import AltoIRAExtractor
from src.security_master.extractor.interactive_brokers import (
    InteractiveBrokersExtractor,
)
from src.security_master.extractor.kubera import KuberaExtractor
from src.security_master.extractor.wells_fargo import WellsFargoExtractor
from src.security_master.pp_integration.json_exporter import PPJSONExporter
from src.security_master.pp_integration.xml_generator import PPXMLGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SecurityMasterInterface:
    """
    Main Security-Master web interface providing comprehensive functionality
    for enterprise portfolio performance and security classification management.
    """

    def __init__(self):
        self.classifier = SecurityClassifier()
        self.benchmark_generator = BenchmarkSecurityGenerator()
        self.pp_xml_generator = PPXMLGenerator()
        self.pp_json_exporter = PPJSONExporter()

        # Institution extractors
        self.extractors = {
            "Wells Fargo": WellsFargoExtractor(),
            "Interactive Brokers": InteractiveBrokersExtractor(),
            "AltoIRA": AltoIRAExtractor(),
            "Kubera": KuberaExtractor(),
        }

        # Cache for performance
        self._securities_cache = {}
        self._analytics_cache = {}
        self._cache_timestamp = None

        # UI state
        self.current_user = None
        self.selected_securities = []

        logger.info("Security-Master interface initialized")

    def create_app(self) -> gr.Blocks:
        """Create the complete Gradio application with all tabs and functionality.

        Returns:
            gr.Blocks: Configured Gradio Blocks application ready to launch.
        """

        # Choose theme based on PromptCraft availability
        if PROMPTCRAFT_AVAILABLE:
            theme = gr.themes.Soft()
        else:
            theme = gr.themes.Default()

        with gr.Blocks(
            title="Security-Master: Enterprise Portfolio Performance System",
            theme=theme,
            css=self._get_custom_css(),
            head=self._get_custom_head(),
        ) as app:

            # Application header with branding
            with gr.Row():
                gr.HTML(self._get_header_html())

            # User context and session info
            with gr.Row(visible=False) as user_context:
                current_user_display = gr.Markdown("**User:** Loading...")
                user_permissions_display = gr.Markdown("**Permissions:** Loading...")

            # Main application tabs
            with gr.Tabs() as main_tabs:

                # Securities Classification and Management
                with gr.Tab("🔍 Securities Classification", id="classification"):
                    self._create_classification_tab()

                # Institution Data Import and Processing
                with gr.Tab("📥 Data Import & Processing", id="import"):
                    self._create_import_tab()

                # Portfolio Analytics and Performance
                with gr.Tab("📊 Portfolio Analytics", id="analytics"):
                    self._create_analytics_tab()

                # Benchmark Management
                with gr.Tab("🎯 Benchmark Management", id="benchmarks"):
                    self._create_benchmark_tab()

                # Portfolio Performance Export
                with gr.Tab("📤 Portfolio Performance Export", id="export"):
                    self._create_export_tab()

                # Data Quality and Validation
                with gr.Tab("✅ Data Quality", id="quality"):
                    self._create_quality_tab()

                # System Administration (admin only)
                with gr.Tab("⚙️ Administration", id="admin"):
                    self._create_admin_tab()

            # Application footer with version and status
            with gr.Row():
                gr.HTML(self._get_footer_html())

            # Initialize application state on load
            app.load(
                fn=self._initialize_app_state,
                outputs=[user_context, current_user_display, user_permissions_display],
            )

        return app

    def _create_classification_tab(self):
        """Create the securities classification and management interface."""

        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("### 🔍 Securities Search & Classification")

                # Search interface
                with gr.Row():
                    search_input = gr.Textbox(
                        label="Search Securities",
                        placeholder="Enter ISIN, Symbol, Name, or CUSIP...",
                        lines=1,
                        interactive=True,
                    )
                    search_type = gr.Dropdown(
                        label="Search Type",
                        choices=["All", "ISIN", "Symbol", "Name", "CUSIP"],
                        value="All",
                        interactive=True,
                    )

                with gr.Row():
                    search_btn = gr.Button("🔍 Search", variant="primary", size="sm")
                    clear_search_btn = gr.Button(
                        "🗑️ Clear",
                        variant="secondary",
                        size="sm",
                    )
                    bulk_classify_btn = gr.Button(
                        "🤖 Bulk Auto-Classify",
                        variant="primary",
                        size="sm",
                    )

                # Search results with selection
                search_results = gr.DataFrame(
                    label="Search Results",
                    headers=[
                        "Select",
                        "Symbol",
                        "Name",
                        "ISIN",
                        "Asset Class",
                        "GICS Sector",
                        "Classification Confidence",
                        "Last Updated",
                    ],
                    datatype=[
                        "bool",
                        "str",
                        "str",
                        "str",
                        "str",
                        "str",
                        "number",
                        "str",
                    ],
                    interactive=True,
                    wrap=True,
                    height=300,
                )

            with gr.Column(scale=1):
                gr.Markdown("### 📊 Classification Statistics")

                # Real-time statistics display
                stats_display = gr.HTML(
                    """
                    <div class="stats-container">
                        <div class="stat-card">
                            <h4>Total Securities</h4>
                            <div class="stat-value" id="total-securities">Loading...</div>
                        </div>
                        <div class="stat-card">
                            <h4>Classified</h4>
                            <div class="stat-value" id="classified-securities">Loading...</div>
                        </div>
                        <div class="stat-card">
                            <h4>Pending Review</h4>
                            <div class="stat-value" id="pending-securities">Loading...</div>
                        </div>
                        <div class="stat-card">
                            <h4>Accuracy Score</h4>
                            <div class="stat-value" id="classification-accuracy">Loading...</div>
                        </div>
                    </div>
                """,
                )

                # Quick action buttons
                with gr.Column():
                    refresh_stats_btn = gr.Button("🔄 Refresh Stats", size="sm")
                    export_classification_report_btn = gr.Button(
                        "📊 Export Report",
                        size="sm",
                    )

        # Manual classification interface
        with gr.Row():
            gr.Markdown("### ✏️ Manual Classification")

        with gr.Row():
            with gr.Column(scale=2):
                selected_security_info = gr.HTML(
                    "Select a security from search results to classify",
                )

                with gr.Row():
                    asset_class_dropdown = gr.Dropdown(
                        label="Asset Class",
                        choices=[
                            "Equity",
                            "Fixed Income",
                            "Cash",
                            "Commodity",
                            "Real Estate",
                            "Alternative",
                            "Derivative",
                        ],
                        interactive=True,
                    )

                    investment_type_dropdown = gr.Dropdown(
                        label="Investment Type",
                        choices=[
                            "Individual Stock",
                            "ETF",
                            "Mutual Fund",
                            "Bond",
                            "Money Market",
                            "REIT",
                            "Option",
                            "Future",
                        ],
                        interactive=True,
                    )

                with gr.Row():
                    gics_sector_dropdown = gr.Dropdown(
                        label="GICS Sector",
                        choices=[
                            "Energy",
                            "Materials",
                            "Industrials",
                            "Consumer Discretionary",
                            "Consumer Staples",
                            "Health Care",
                            "Financials",
                            "Information Technology",
                            "Communication Services",
                            "Utilities",
                            "Real Estate",
                        ],
                        interactive=True,
                    )

                    gics_industry_dropdown = gr.Dropdown(
                        label="GICS Industry",
                        choices=[],  # Populated based on sector selection
                        interactive=True,
                    )

                with gr.Row():
                    trbc_classification = gr.Dropdown(
                        label="TRBC Business Classification",
                        choices=[
                            "Basic Materials",
                            "Consumer Cyclicals",
                            "Consumer Non-Cyclicals",
                            "Energy",
                            "Financial Services",
                            "Healthcare",
                            "Industrial",
                            "Technology",
                            "Telecommunications",
                            "Utilities",
                        ],
                        interactive=True,
                    )

                    cfi_code = gr.Textbox(
                        label="CFI Code",
                        placeholder="e.g., ESVUFR",
                        max_lines=1,
                        interactive=True,
                    )

            with gr.Column(scale=1):
                # Classification confidence and source
                confidence_slider = gr.Slider(
                    label="Classification Confidence",
                    minimum=0.0,
                    maximum=1.0,
                    value=0.95,
                    step=0.05,
                    interactive=True,
                )

                classification_source = gr.Dropdown(
                    label="Classification Source",
                    choices=[
                        "Manual Override",
                        "OpenFIGI API",
                        "pp-portfolio-classifier",
                        "Alpha Vantage",
                        "Internal Database",
                    ],
                    value="Manual Override",
                    interactive=True,
                )

                # Classification notes
                classification_notes = gr.Textbox(
                    label="Classification Notes",
                    placeholder="Add reasoning, research notes, or special considerations...",
                    lines=4,
                    interactive=True,
                )

        # Classification action buttons
        with gr.Row():
            save_classification_btn = gr.Button(
                "💾 Save Classification",
                variant="primary",
            )
            auto_classify_selected_btn = gr.Button(
                "🤖 Auto-Classify Selected",
                variant="secondary",
            )
            review_classification_btn = gr.Button(
                "👁️ Review & Approve",
                variant="secondary",
            )
            reject_classification_btn = gr.Button(
                "❌ Reject Classification",
                variant="stop",
            )

        # Classification result feedback
        classification_result = gr.Markdown()

        # Event handlers for classification tab
        self._setup_classification_handlers(
            search_btn,
            search_input,
            search_type,
            search_results,
            save_classification_btn,
            auto_classify_selected_btn,
            classification_result,
            stats_display,
        )

    def _create_import_tab(self):
        """Create the institution data import and processing interface."""

        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("### 📥 Institution Data Import")

                # File upload interface
                file_upload = gr.File(
                    label="Select File to Import",
                    file_types=[".csv", ".xml", ".pdf", ".json", ".xlsx"],
                    file_count="single",
                    height=100,
                )

                with gr.Row():
                    institution_type = gr.Dropdown(
                        label="Institution Type",
                        choices=list(self.extractors.keys()),
                        interactive=True,
                    )

                    account_type = gr.Dropdown(
                        label="Account Type",
                        choices=[
                            "Taxable",
                            "IRA Traditional",
                            "IRA Roth",
                            "401k",
                            "Trust",
                            "Corporate",
                            "Other",
                        ],
                        interactive=True,
                    )

                # Import options and settings
                import_options = gr.CheckboxGroup(
                    label="Import Options",
                    choices=[
                        "Auto-classify securities during import",
                        "Validate against existing data",
                        "Generate data quality report",
                        "Update Portfolio Performance data",
                        "Create benchmark securities",
                        "Send notifications on completion",
                    ],
                    value=[
                        "Auto-classify securities during import",
                        "Validate against existing data",
                    ],
                )

                # Import processing options
                with gr.Row():
                    duplicate_handling = gr.Dropdown(
                        label="Duplicate Handling",
                        choices=[
                            "Skip duplicates",
                            "Update existing",
                            "Create new version",
                            "Merge data",
                        ],
                        value="Update existing",
                        interactive=True,
                    )

                    validation_level = gr.Dropdown(
                        label="Validation Level",
                        choices=["Basic", "Standard", "Strict", "Custom"],
                        value="Standard",
                        interactive=True,
                    )

            with gr.Column(scale=1):
                gr.Markdown("### 📋 Import History")

                import_history = gr.DataFrame(
                    label="Recent Imports",
                    headers=[
                        "Date",
                        "Institution",
                        "File",
                        "Records",
                        "Success",
                        "Issues",
                    ],
                    max_rows=15,
                    height=300,
                )

                with gr.Column():
                    refresh_history_btn = gr.Button("🔄 Refresh", size="sm")
                    export_history_btn = gr.Button("📊 Export History", size="sm")

        # Import action buttons
        with gr.Row():
            validate_only_btn = gr.Button("✅ Validate Only", variant="secondary")
            import_file_btn = gr.Button("📥 Import File", variant="primary")
            schedule_import_btn = gr.Button("⏰ Schedule Import", variant="secondary")

        # Import status and progress
        with gr.Row():
            import_status = gr.Markdown()
            import_progress = gr.Progress()

        # Import results and analysis
        with gr.Row():
            with gr.Column(scale=2):
                import_results = gr.DataFrame(
                    label="Import Results & Issues",
                    headers=[
                        "Row",
                        "Security",
                        "Issue Type",
                        "Status",
                        "Classification",
                        "Action Required",
                        "Notes",
                    ],
                    height=400,
                )

            with gr.Column(scale=1):
                import_summary = gr.JSON(label="Import Summary", visible=False)

                data_quality_report = gr.HTML(label="Data Quality Report")

        # Setup import event handlers
        self._setup_import_handlers(
            import_file_btn,
            file_upload,
            institution_type,
            import_options,
            import_status,
            import_results,
            import_history,
        )

    def _create_analytics_tab(self):
        """Create the portfolio analytics and performance analysis interface."""

        with gr.Row():
            with gr.Column():
                gr.Markdown("### 📊 Portfolio Performance Analytics")

                # Portfolio selection and configuration
                with gr.Row():
                    portfolio_selector = gr.Dropdown(
                        label="Select Portfolio/Account",
                        choices=[],  # Populated from database
                        interactive=True,
                        multiselect=False,
                    )

                    comparison_portfolios = gr.Dropdown(
                        label="Comparison Portfolios (Optional)",
                        choices=[],  # Populated from database
                        interactive=True,
                        multiselect=True,
                    )

                # Analysis period and benchmark selection
                with gr.Row():
                    analysis_start_date = gr.DatePicker(
                        label="Analysis Start Date",
                        value=date.today() - timedelta(days=365),
                        interactive=True,
                    )

                    analysis_end_date = gr.DatePicker(
                        label="Analysis End Date",
                        value=date.today(),
                        interactive=True,
                    )

                    benchmark_selector = gr.Dropdown(
                        label="Benchmark",
                        choices=[],  # Populated with synthetic and standard benchmarks
                        interactive=True,
                    )

                # Analytics configuration
                analytics_options = gr.CheckboxGroup(
                    label="Analytics to Generate",
                    choices=[
                        "Performance Metrics (Sharpe, Alpha, Beta)",
                        "Risk Analysis (VaR, Tracking Error)",
                        "Asset Allocation Analysis",
                        "Performance Attribution",
                        "Monte Carlo Simulation",
                        "Sector/Security Contribution Analysis",
                    ],
                    value=[
                        "Performance Metrics (Sharpe, Alpha, Beta)",
                        "Risk Analysis (VaR, Tracking Error)",
                    ],
                )

                # Generate analytics
                with gr.Row():
                    generate_analytics_btn = gr.Button(
                        "📊 Generate Analytics",
                        variant="primary",
                    )
                    export_analytics_btn = gr.Button(
                        "📤 Export Results",
                        variant="secondary",
                    )
                    schedule_analytics_btn = gr.Button(
                        "⏰ Schedule Regular Reports",
                        variant="secondary",
                    )

        # Analytics results display
        with gr.Tabs():
            with gr.Tab("Performance Metrics"):
                with gr.Row():
                    with gr.Column():
                        performance_metrics = gr.DataFrame(
                            label="Key Performance Metrics",
                            headers=[
                                "Metric",
                                "Portfolio",
                                "Benchmark",
                                "Relative Performance",
                                "Percentile",
                            ],
                            height=300,
                        )

                    with gr.Column():
                        risk_metrics = gr.DataFrame(
                            label="Risk Metrics",
                            headers=[
                                "Risk Measure",
                                "Value",
                                "1Y Historical",
                                "Peer Percentile",
                                "Status",
                            ],
                            height=300,
                        )

            with gr.Tab("Performance Charts"):
                with gr.Column():
                    performance_chart = gr.Plot(
                        label="Cumulative Performance Comparison",
                        height=400,
                    )

                    rolling_metrics_chart = gr.Plot(
                        label="Rolling Performance Metrics",
                        height=300,
                    )

            with gr.Tab("Asset Allocation"):
                with gr.Row():
                    with gr.Column():
                        allocation_chart = gr.Plot(
                            label="Current Asset Allocation",
                            height=400,
                        )

                    with gr.Column():
                        allocation_drift = gr.DataFrame(
                            label="Allocation vs Target",
                            headers=[
                                "Asset Class",
                                "Current %",
                                "Target %",
                                "Drift",
                                "Action Needed",
                            ],
                            height=400,
                        )

            with gr.Tab("Attribution Analysis"):
                attribution_results = gr.DataFrame(
                    label="Performance Attribution",
                    headers=[
                        "Security/Sector",
                        "Weight %",
                        "Return %",
                        "Contribution",
                        "Relative to Benchmark",
                    ],
                    height=500,
                )

        # Setup analytics event handlers
        self._setup_analytics_handlers(
            generate_analytics_btn,
            portfolio_selector,
            benchmark_selector,
            analysis_start_date,
            analysis_end_date,
            performance_metrics,
            risk_metrics,
            performance_chart,
        )

    def _create_benchmark_tab(self):
        """Create the benchmark management interface."""

        with gr.Row():
            with gr.Column():
                gr.Markdown("### 🎯 Benchmark Security Management")

                # Existing benchmarks
                existing_benchmarks = gr.DataFrame(
                    label="Existing Benchmark Securities",
                    headers=[
                        "Name",
                        "Symbol",
                        "Type",
                        "Base Date",
                        "Last Updated",
                        "Status",
                        "Actions",
                    ],
                    height=200,
                )

                with gr.Row():
                    refresh_benchmarks_btn = gr.Button("🔄 Refresh", size="sm")
                    delete_benchmark_btn = gr.Button(
                        "🗑️ Delete Selected",
                        variant="stop",
                        size="sm",
                    )

        with gr.Tabs():
            with gr.Tab("Create Portfolio Benchmark"):
                with gr.Row():
                    with gr.Column():
                        source_portfolio = gr.Dropdown(
                            label="Source Portfolio",
                            choices=[],  # Populated from database
                            interactive=True,
                        )

                        benchmark_name = gr.Textbox(
                            label="Benchmark Name",
                            placeholder="e.g., Conservative Growth Model",
                            interactive=True,
                        )

                        benchmark_symbol = gr.Textbox(
                            label="Symbol",
                            placeholder="e.g., CGM",
                            max_lines=1,
                            interactive=True,
                        )

                    with gr.Column():
                        benchmark_start_date = gr.DatePicker(
                            label="Benchmark Start Date",
                            value=date(2023, 1, 1),
                            interactive=True,
                        )

                        rebalance_frequency = gr.Dropdown(
                            label="Rebalancing Frequency",
                            choices=[
                                "Daily",
                                "Weekly",
                                "Monthly",
                                "Quarterly",
                                "Annually",
                            ],
                            value="Monthly",
                            interactive=True,
                        )

                        base_value = gr.Number(
                            label="Base Value",
                            value=100.00,
                            precision=2,
                            interactive=True,
                        )

                create_portfolio_benchmark_btn = gr.Button(
                    "🎯 Create Portfolio Benchmark",
                    variant="primary",
                )

            with gr.Tab("Create Custom Index"):
                with gr.Row():
                    with gr.Column():
                        custom_benchmark_name = gr.Textbox(
                            label="Custom Benchmark Name",
                            placeholder="e.g., 60/40 Allocation",
                            interactive=True,
                        )

                        custom_benchmark_symbol = gr.Textbox(
                            label="Symbol",
                            placeholder="e.g., CUST60",
                            max_lines=1,
                            interactive=True,
                        )

                    with gr.Column():
                        custom_start_date = gr.DatePicker(
                            label="Start Date",
                            value=date(2023, 1, 1),
                            interactive=True,
                        )

                        custom_rebalance_frequency = gr.Dropdown(
                            label="Rebalancing Frequency",
                            choices=["Daily", "Weekly", "Monthly", "Quarterly"],
                            value="Monthly",
                            interactive=True,
                        )

                # Securities and weights configuration
                securities_weights_config = gr.DataFrame(
                    label="Securities and Weights Configuration",
                    headers=["Security", "Symbol", "Weight %", "Remove"],
                    datatype=["str", "str", "number", "bool"],
                    interactive=True,
                    height=300,
                )

                with gr.Row():
                    add_security_btn = gr.Button("➕ Add Security", size="sm")
                    normalize_weights_btn = gr.Button("⚖️ Normalize Weights", size="sm")
                    validate_config_btn = gr.Button(
                        "✅ Validate Configuration",
                        size="sm",
                    )

                create_custom_benchmark_btn = gr.Button(
                    "🎯 Create Custom Index Benchmark",
                    variant="primary",
                )

        # Benchmark creation results
        benchmark_creation_result = gr.Markdown()

        # Setup benchmark event handlers
        self._setup_benchmark_handlers(
            create_portfolio_benchmark_btn,
            source_portfolio,
            benchmark_name,
            create_custom_benchmark_btn,
            securities_weights_config,
            benchmark_creation_result,
            existing_benchmarks,
        )

    def _create_export_tab(self):
        """Create the Portfolio Performance export interface."""

        with gr.Row():
            with gr.Column():
                gr.Markdown("### 📤 Portfolio Performance Export Generation")

                # Client/Portfolio selection
                export_client_selector = gr.Dropdown(
                    label="Select Client/Portfolio for Export",
                    choices=[],  # Populated from database
                    interactive=True,
                )

                # Export configuration
                export_options = gr.CheckboxGroup(
                    label="Export Options",
                    choices=[
                        "Include synthetic benchmark securities",
                        "Include complete transaction history",
                        "Include daily price history",
                        "Include security classifications and metadata",
                        "Include portfolio analytics data",
                        "Validate XML structure before export",
                        "Generate export verification report",
                    ],
                    value=[
                        "Include synthetic benchmark securities",
                        "Validate XML structure before export",
                    ],
                )

                with gr.Row():
                    export_format = gr.Radio(
                        label="Export Format",
                        choices=[
                            "Portfolio Performance XML",
                            "JSON Data Export",
                            "Both Formats",
                        ],
                        value="Portfolio Performance XML",
                        interactive=True,
                    )

                    export_compression = gr.Checkbox(
                        label="Compress Export Files",
                        value=True,
                        interactive=True,
                    )

                # Date range for export
                with gr.Row():
                    export_start_date = gr.DatePicker(
                        label="Export Start Date",
                        value=date(2020, 1, 1),
                        interactive=True,
                    )

                    export_end_date = gr.DatePicker(
                        label="Export End Date",
                        value=date.today(),
                        interactive=True,
                    )

        # Export generation
        with gr.Row():
            generate_export_btn = gr.Button("📤 Generate Export", variant="primary")
            preview_export_btn = gr.Button("👁️ Preview Export", variant="secondary")
            schedule_export_btn = gr.Button(
                "⏰ Schedule Regular Export",
                variant="secondary",
            )

        # Export status and results
        export_status = gr.Markdown()
        export_progress = gr.Progress()

        with gr.Tabs():
            with gr.Tab("Export Preview"):
                with gr.Row():
                    with gr.Column(scale=2):
                        export_preview = gr.Code(
                            label="Export File Preview",
                            language="xml",
                            lines=25,
                            interactive=False,
                        )

                    with gr.Column(scale=1):
                        export_statistics = gr.DataFrame(
                            label="Export Statistics",
                            headers=["Category", "Count", "Size", "Status"],
                            height=400,
                        )

            with gr.Tab("Download & Validation"):
                with gr.Column():
                    export_download = gr.File(
                        label="Download Export File",
                        visible=False,
                    )

                    validation_results = gr.DataFrame(
                        label="Export Validation Results",
                        headers=["Check", "Status", "Details", "Action Required"],
                        height=300,
                    )

                    export_verification_report = gr.File(
                        label="Download Verification Report",
                        visible=False,
                    )

        # Setup export event handlers
        self._setup_export_handlers(
            generate_export_btn,
            export_client_selector,
            export_options,
            export_format,
            export_status,
            export_preview,
            export_statistics,
            export_download,
        )

    def _create_quality_tab(self):
        """Create the data quality and validation interface."""

        with gr.Row():
            with gr.Column():
                gr.Markdown("### ✅ Data Quality Dashboard")

                # Overall quality score
                overall_quality_score = gr.HTML(
                    """
                    <div class="quality-dashboard">
                        <div class="quality-score-card">
                            <h3>Overall Data Quality Score</h3>
                            <div class="quality-score" id="overall-score">Loading...</div>
                            <div class="quality-trend" id="quality-trend">Loading...</div>
                        </div>
                    </div>
                """,
                )

        with gr.Tabs():
            with gr.Tab("Quality Metrics"):
                with gr.Row():
                    institution_quality = gr.DataFrame(
                        label="Institution Data Quality",
                        headers=[
                            "Institution",
                            "Completeness",
                            "Accuracy",
                            "Consistency",
                            "Timeliness",
                            "Overall Score",
                        ],
                        height=200,
                    )

                with gr.Row():
                    security_quality = gr.DataFrame(
                        label="Security Classification Quality",
                        headers=[
                            "Category",
                            "Total",
                            "Classified",
                            "High Confidence",
                            "Needs Review",
                            "Quality Score",
                        ],
                        height=200,
                    )

            with gr.Tab("Validation Issues"):
                validation_issues = gr.DataFrame(
                    label="Data Validation Issues",
                    headers=[
                        "Issue Type",
                        "Severity",
                        "Count",
                        "Institution",
                        "Last Detected",
                        "Status",
                        "Action Required",
                    ],
                    height=400,
                )

                with gr.Row():
                    resolve_issue_btn = gr.Button(
                        "✅ Mark as Resolved",
                        variant="primary",
                        size="sm",
                    )
                    bulk_resolve_btn = gr.Button(
                        "🔄 Bulk Resolve",
                        variant="secondary",
                        size="sm",
                    )
                    export_issues_btn = gr.Button("📊 Export Issues Report", size="sm")

            with gr.Tab("Quality Trends"):
                quality_trend_chart = gr.Plot(
                    label="Data Quality Trends Over Time",
                    height=500,
                )

                quality_breakdown_chart = gr.Plot(
                    label="Quality Score Breakdown by Category",
                    height=300,
                )

        # Quality monitoring controls
        with gr.Row():
            refresh_quality_btn = gr.Button(
                "🔄 Refresh Quality Metrics",
                variant="primary",
            )
            run_validation_btn = gr.Button(
                "🔍 Run Full Validation",
                variant="secondary",
            )
            schedule_quality_btn = gr.Button(
                "⏰ Schedule Quality Checks",
                variant="secondary",
            )

        # Setup quality event handlers
        self._setup_quality_handlers(
            refresh_quality_btn,
            institution_quality,
            security_quality,
            validation_issues,
            quality_trend_chart,
        )

    def _create_admin_tab(self):
        """Create the system administration interface."""

        with gr.Row():
            gr.Markdown("### ⚙️ System Administration")

        with gr.Tabs():
            with gr.Tab("System Status"):
                with gr.Row():
                    system_health = gr.DataFrame(
                        label="System Health Status",
                        headers=[
                            "Component",
                            "Status",
                            "Last Check",
                            "Response Time",
                            "Details",
                        ],
                        height=200,
                    )

                with gr.Row():
                    service_status = gr.DataFrame(
                        label="Service Status",
                        headers=[
                            "Service",
                            "Status",
                            "Uptime",
                            "Memory Usage",
                            "CPU Usage",
                            "Actions",
                        ],
                        height=200,
                    )

                with gr.Row():
                    refresh_status_btn = gr.Button("🔄 Refresh Status", size="sm")
                    restart_services_btn = gr.Button(
                        "🔄 Restart Services",
                        variant="stop",
                        size="sm",
                    )
                    run_diagnostics_btn = gr.Button(
                        "🔧 Run Diagnostics",
                        variant="secondary",
                        size="sm",
                    )

            with gr.Tab("User Management"):
                with gr.Row():
                    active_users = gr.DataFrame(
                        label="Active Users",
                        headers=[
                            "Email",
                            "Name",
                            "Role",
                            "Last Login",
                            "Session Status",
                            "Permissions",
                        ],
                        height=250,
                    )

                with gr.Row():
                    user_audit_log = gr.DataFrame(
                        label="Recent User Activity",
                        headers=[
                            "User",
                            "Action",
                            "Resource",
                            "Timestamp",
                            "IP Address",
                            "Result",
                        ],
                        height=250,
                    )

                # User management controls
                with gr.Row():
                    refresh_users_btn = gr.Button("🔄 Refresh", size="sm")
                    export_audit_btn = gr.Button("📊 Export Audit Log", size="sm")
                    manage_permissions_btn = gr.Button(
                        "🔑 Manage Permissions",
                        size="sm",
                    )

            with gr.Tab("API Management"):
                api_usage = gr.DataFrame(
                    label="External API Usage",
                    headers=[
                        "API",
                        "Requests Today",
                        "Rate Limit",
                        "Success Rate",
                        "Avg Response Time",
                        "Status",
                    ],
                    height=200,
                )

                api_keys_status = gr.DataFrame(
                    label="API Keys Status",
                    headers=[
                        "Service",
                        "Key Status",
                        "Expires",
                        "Usage",
                        "Last Rotated",
                        "Actions",
                    ],
                    height=200,
                )

                with gr.Row():
                    rotate_keys_btn = gr.Button(
                        "🔄 Rotate API Keys",
                        variant="secondary",
                        size="sm",
                    )
                    test_apis_btn = gr.Button("🧪 Test API Connections", size="sm")

            with gr.Tab("System Configuration"):
                with gr.Row():
                    config_editor = gr.JSON(label="System Configuration", height=400)

                with gr.Row():
                    save_config_btn = gr.Button(
                        "💾 Save Configuration",
                        variant="primary",
                    )
                    reload_config_btn = gr.Button(
                        "🔄 Reload Configuration",
                        variant="secondary",
                    )
                    backup_config_btn = gr.Button("📦 Backup Configuration", size="sm")

        # Setup admin event handlers
        self._setup_admin_handlers(
            refresh_status_btn,
            system_health,
            service_status,
            active_users,
            user_audit_log,
            api_usage,
        )

    # Event handler setup methods
    def _setup_classification_handlers(
        self,
        search_btn: Any,
        search_input: Any,
        search_type: Any,
        search_results: Any,
        save_btn: Any,
        auto_classify_btn: Any,
        result_display: Any,
        stats_display: Any,
    ):
        """Setup event handlers for classification tab.

        Args:
            search_btn (Any): Gradio button that triggers search.
            search_input (Any): Gradio text input for the search query.
            search_type (Any): Gradio dropdown for search type selection.
            search_results (Any): Gradio component to display search results.
            save_btn (Any): Gradio button to save manual classification.
            auto_classify_btn (Any): Gradio button to trigger auto-classification.
            result_display (Any): Gradio component to display classification result.
            stats_display (Any): Gradio component to display statistics.
        """

        search_btn.click(
            fn=self._search_securities,
            inputs=[search_input, search_type],
            outputs=[search_results, stats_display],
        )

        save_btn.click(
            fn=self._save_manual_classification,
            inputs=[],  # Would include all classification form inputs
            outputs=[result_display, stats_display],
        )

    def _setup_import_handlers(
        self,
        import_btn: Any,
        file_upload: Any,
        institution_type: Any,
        options: Any,
        status_display: Any,
        results_display: Any,
        history_display: Any,
    ):
        """Setup event handlers for import tab.

        Args:
            import_btn (Any): Gradio button that triggers the import.
            file_upload (Any): Gradio file upload component.
            institution_type (Any): Gradio dropdown for institution type.
            options (Any): Gradio component for import options.
            status_display (Any): Gradio component to display import status.
            results_display (Any): Gradio component to display results.
            history_display (Any): Gradio component to display import history.
        """

        import_btn.click(
            fn=self._process_institution_import,
            inputs=[file_upload, institution_type, options],
            outputs=[status_display, results_display, history_display],
        )

    def _setup_analytics_handlers(
        self,
        generate_btn: Any,
        portfolio_selector: Any,
        benchmark_selector: Any,
        start_date: Any,
        end_date: Any,
        metrics_display: Any,
        risk_display: Any,
        chart_display: Any,
    ):
        """Setup event handlers for analytics tab.

        Args:
            generate_btn (Any): Gradio button that triggers analytics generation.
            portfolio_selector (Any): Gradio dropdown for portfolio selection.
            benchmark_selector (Any): Gradio dropdown for benchmark selection.
            start_date (Any): Gradio date input for the analysis start date.
            end_date (Any): Gradio date input for the analysis end date.
            metrics_display (Any): Gradio component to display performance metrics.
            risk_display (Any): Gradio component to display risk metrics.
            chart_display (Any): Gradio component to display performance chart.
        """

        generate_btn.click(
            fn=self._generate_portfolio_analytics,
            inputs=[portfolio_selector, benchmark_selector, start_date, end_date],
            outputs=[metrics_display, risk_display, chart_display],
        )

    def _setup_benchmark_handlers(
        self,
        create_portfolio_btn: Any,
        source_portfolio: Any,
        benchmark_name: Any,
        create_custom_btn: Any,
        securities_config: Any,
        result_display: Any,
        benchmarks_display: Any,
    ):
        """Setup event handlers for benchmark tab.

        Args:
            create_portfolio_btn (Any): Gradio button to create a portfolio benchmark.
            source_portfolio (Any): Gradio dropdown for source portfolio selection.
            benchmark_name (Any): Gradio text input for the benchmark name.
            create_custom_btn (Any): Gradio button to create a custom index benchmark.
            securities_config (Any): Gradio component for custom securities configuration.
            result_display (Any): Gradio component to display the creation result.
            benchmarks_display (Any): Gradio component to display existing benchmarks.
        """

        create_portfolio_btn.click(
            fn=self._create_portfolio_benchmark,
            inputs=[source_portfolio, benchmark_name],
            outputs=[result_display, benchmarks_display],
        )

    def _setup_export_handlers(
        self,
        generate_btn: Any,
        client_selector: Any,
        options: Any,
        format_selector: Any,
        status_display: Any,
        preview_display: Any,
        stats_display: Any,
        download_file: Any,
    ):
        """Setup event handlers for export tab.

        Args:
            generate_btn (Any): Gradio button that triggers export generation.
            client_selector (Any): Gradio dropdown for client selection.
            options (Any): Gradio component for export options.
            format_selector (Any): Gradio dropdown for export format selection.
            status_display (Any): Gradio component to display export status.
            preview_display (Any): Gradio component to preview the export.
            stats_display (Any): Gradio component to display export statistics.
            download_file (Any): Gradio file component for downloading the export.
        """

        generate_btn.click(
            fn=self._generate_pp_export,
            inputs=[client_selector, options, format_selector],
            outputs=[status_display, preview_display, stats_display, download_file],
        )

    def _setup_quality_handlers(
        self,
        refresh_btn: Any,
        institution_quality: Any,
        security_quality: Any,
        validation_issues: Any,
        trend_chart: Any,
    ):
        """Setup event handlers for quality tab.

        Args:
            refresh_btn (Any): Gradio button that triggers quality metrics refresh.
            institution_quality (Any): Gradio component for institution quality display.
            security_quality (Any): Gradio component for security quality display.
            validation_issues (Any): Gradio component for validation issues display.
            trend_chart (Any): Gradio component for quality trend chart.
        """

        refresh_btn.click(
            fn=self._refresh_quality_metrics,
            outputs=[
                institution_quality,
                security_quality,
                validation_issues,
                trend_chart,
            ],
        )

    def _setup_admin_handlers(
        self,
        refresh_btn: Any,
        system_health: Any,
        service_status: Any,
        users_display: Any,
        audit_display: Any,
        api_display: Any,
    ):
        """Setup event handlers for admin tab.

        Args:
            refresh_btn (Any): Gradio button that triggers system status refresh.
            system_health (Any): Gradio component for system health display.
            service_status (Any): Gradio component for service status display.
            users_display (Any): Gradio component for users display.
            audit_display (Any): Gradio component for audit log display.
            api_display (Any): Gradio component for API usage display.
        """

        refresh_btn.click(
            fn=self._refresh_system_status,
            outputs=[
                system_health,
                service_status,
                users_display,
                audit_display,
                api_display,
            ],
        )

    # Core functionality methods (implementations would be complete)
    def _initialize_app_state(self):
        """Initialize application state on load."""
        # Implementation would set up user context and permissions
        return (
            gr.update(visible=True),
            "**User:** Admin",
            "**Permissions:** Full Access",
        )

    def _search_securities(
        self,
        query: str,
        search_type: str,
    ) -> tuple[pd.DataFrame, str]:
        """Search securities based on query and type.

        Args:
            query (str): Search query string.
            search_type (str): Type of search (e.g., symbol, name, ISIN).

        Returns:
            tuple[pd.DataFrame, str]: Search results dataframe and HTML stats string.
        """
        # Implementation would query database and return results
        sample_data = pd.DataFrame(
            {
                "Select": [False] * 5,
                "Symbol": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
                "Name": [
                    "Apple Inc.",
                    "Microsoft Corp.",
                    "Alphabet Inc.",
                    "Amazon.com Inc.",
                    "Tesla Inc.",
                ],
                "ISIN": [
                    "US0378331005",
                    "US5949181045",
                    "US02079K3059",
                    "US0231351067",
                    "US88160R1014",
                ],
                "Asset Class": ["Equity"] * 5,
                "GICS Sector": [
                    "Technology",
                    "Technology",
                    "Communication Services",
                    "Consumer Discretionary",
                    "Consumer Discretionary",
                ],
                "Classification Confidence": [0.98, 0.97, 0.99, 0.96, 0.95],
                "Last Updated": ["2024-01-15"] * 5,
            },
        )

        stats_html = """
            <div class="stats-container">
                <div class="stat-card">
                    <h4>Total Securities</h4>
                    <div class="stat-value">15,247</div>
                </div>
                <div class="stat-card">
                    <h4>Classified</h4>
                    <div class="stat-value">14,832 (97.3%)</div>
                </div>
                <div class="stat-card">
                    <h4>Pending Review</h4>
                    <div class="stat-value">415</div>
                </div>
                <div class="stat-card">
                    <h4>Accuracy Score</h4>
                    <div class="stat-value">96.8%</div>
                </div>
            </div>
        """

        return sample_data, stats_html

    def _save_manual_classification(self) -> str:
        """Save manual classification.

        Returns:
            str: Success or error status message.
        """
        return "✅ Classification saved successfully"

    def _process_institution_import(
        self,
        file: Any,
        institution: str,
        options: list[str],
    ) -> tuple[str, pd.DataFrame, pd.DataFrame]:
        """Process institution file import.

        Args:
            file (Any): Uploaded file object from Gradio file component.
            institution (str): Institution type identifier (e.g., "Wells Fargo").
            options (list[str]): Import options selected by the user.

        Returns:
            tuple[str, pd.DataFrame, pd.DataFrame]: Status message, results dataframe, and history dataframe.
        """
        # Implementation would process file and return results
        status = "✅ File imported successfully. Processed 1,247 transactions, classified 987 securities."

        results_data = pd.DataFrame(
            {
                "Row": [1, 2, 3, 4, 5],
                "Security": ["AAPL", "MSFT", "BOND123", "CASH", "UNKNOWN"],
                "Issue Type": ["None", "None", "Missing ISIN", "None", "Unclassified"],
                "Status": ["Success", "Success", "Warning", "Success", "Error"],
                "Classification": [
                    "Technology Stock",
                    "Technology Stock",
                    "Corporate Bond",
                    "Cash",
                    "Unknown",
                ],
                "Action Required": [
                    "None",
                    "None",
                    "Manual Review",
                    "None",
                    "Manual Classification",
                ],
                "Notes": [
                    "",
                    "",
                    "Bond missing ISIN",
                    "",
                    "Security not found in databases",
                ],
            },
        )

        history_data = pd.DataFrame(
            {
                "Date": ["2024-01-15", "2024-01-14", "2024-01-13"],
                "Institution": ["Wells Fargo", "Interactive Brokers", "AltoIRA"],
                "File": ["portfolio_2024.csv", "trades_jan.xml", "statement.pdf"],
                "Records": [1247, 856, 342],
                "Success": ["97.8%", "99.1%", "89.5%"],
                "Issues": [3, 1, 12],
            },
        )

        return status, results_data, history_data

    def _generate_portfolio_analytics(
        self,
        portfolio: str,
        benchmark: str,
        start_date: Any,
        end_date: Any,
    ):
        """Generate portfolio analytics.

        Args:
            portfolio (str): Portfolio identifier to analyze.
            benchmark (str): Benchmark identifier for comparison.
            start_date (Any): Gradio date input value for analysis start.
            end_date (Any): Gradio date input value for analysis end.
        """
        # Implementation would calculate analytics and return results

        metrics_data = pd.DataFrame(
            {
                "Metric": [
                    "Total Return",
                    "Sharpe Ratio",
                    "Alpha",
                    "Beta",
                    "Max Drawdown",
                ],
                "Portfolio": ["12.5%", "0.87", "2.3%", "0.95", "-8.2%"],
                "Benchmark": ["10.2%", "0.75", "0.0%", "1.00", "-9.5%"],
                "Relative Performance": ["+2.3%", "+0.12", "+2.3%", "-0.05", "+1.3%"],
                "Percentile": ["72nd", "68th", "75th", "45th", "62nd"],
            },
        )

        risk_data = pd.DataFrame(
            {
                "Risk Measure": [
                    "Volatility",
                    "VaR (95%)",
                    "Tracking Error",
                    "Information Ratio",
                    "Correlation",
                ],
                "Value": ["14.2%", "-2.1%", "3.8%", "0.61", "0.94"],
                "1Y Historical": ["15.1%", "-2.8%", "4.2%", "0.55", "0.92"],
                "Peer Percentile": ["35th", "25th", "60th", "70th", "85th"],
                "Status": ["Good", "Good", "Moderate", "Good", "High"],
            },
        )

        # Create sample performance chart
        fig = go.Figure()
        dates = pd.date_range(start=start_date, end=end_date, freq="D")
        portfolio_values = [100 * (1.125) ** (i / 365) for i in range(len(dates))]
        benchmark_values = [100 * (1.102) ** (i / 365) for i in range(len(dates))]

        fig.add_trace(
            go.Scatter(
                x=dates,
                y=portfolio_values,
                name="Portfolio",
                line=dict(color="blue"),
            ),
        )
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=benchmark_values,
                name="Benchmark",
                line=dict(color="red"),
            ),
        )
        fig.update_layout(
            title="Cumulative Performance Comparison",
            xaxis_title="Date",
            yaxis_title="Value",
        )

        return metrics_data, risk_data, fig

    def _create_portfolio_benchmark(
        self,
        source_portfolio: str,
        benchmark_name: str,
    ) -> tuple[str, pd.DataFrame]:
        """Create portfolio benchmark.

        Args:
            source_portfolio (str): Source portfolio ID to replicate as benchmark.
            benchmark_name (str): Name for the new benchmark security.

        Returns:
            tuple[str, pd.DataFrame]: Status message and updated benchmarks dataframe.
        """
        result = (
            f"✅ Created portfolio benchmark '{benchmark_name}' from {source_portfolio}"
        )

        benchmarks_data = pd.DataFrame(
            {
                "Name": [benchmark_name, "60/40 Allocation", "Tech Focus"],
                "Symbol": ["PGBM", "ALLOC6040", "TECH"],
                "Type": ["Portfolio", "Custom", "Sector"],
                "Base Date": ["2024-01-15", "2023-01-01", "2023-06-01"],
                "Last Updated": ["2024-01-15", "2024-01-14", "2024-01-13"],
                "Status": ["Active", "Active", "Active"],
                "Actions": ["Edit", "Edit", "Edit"],
            },
        )

        return result, benchmarks_data

    def _generate_pp_export(self, client: str, options: list[str], format: str):
        """Generate Portfolio Performance export.

        Args:
            client (str): Client configuration name to export.
            options (list[str]): Export options (e.g., include prices, include transactions).
            format (str): Export format (e.g., xml, json).
        """
        status = (
            f"✅ Generated {format} export for {client} with {len(options)} options"
        )

        preview = """<?xml version="1.0" encoding="UTF-8"?>
<client version="66">
    <settings>
        <bookmarks>
            <bookmark label="All Securities"/>
        </bookmarks>
    </settings>
    <securities>
        <security>
            <uuid>12345678-1234-1234-1234-123456789012</uuid>
            <name>Apple Inc.</name>
            <isin>US0378331005</isin>
            <tickerSymbol>AAPL</tickerSymbol>
            <currency>USD</currency>
            <prices>
                <price date="2024-01-15" value="150.00"/>
            </prices>
        </security>
    </securities>
</client>"""

        stats_data = pd.DataFrame(
            {
                "Category": ["Securities", "Transactions", "Prices", "Benchmarks"],
                "Count": [1247, 5432, 87654, 3],
                "Size": ["2.4 MB", "8.7 MB", "45.2 MB", "1.1 MB"],
                "Status": ["✅", "✅", "✅", "✅"],
            },
        )

        return status, preview, stats_data, None

    def _refresh_quality_metrics(self):
        """Refresh data quality metrics."""
        institution_data = pd.DataFrame(
            {
                "Institution": [
                    "Wells Fargo",
                    "Interactive Brokers",
                    "AltoIRA",
                    "Kubera",
                ],
                "Completeness": ["98.5%", "99.2%", "87.3%", "95.8%"],
                "Accuracy": ["96.8%", "98.9%", "89.5%", "94.2%"],
                "Consistency": ["97.2%", "98.1%", "91.7%", "96.1%"],
                "Timeliness": ["99.1%", "98.8%", "85.2%", "97.3%"],
                "Overall Score": ["97.9%", "98.8%", "88.4%", "95.9%"],
            },
        )

        security_data = pd.DataFrame(
            {
                "Category": [
                    "Equities",
                    "Fixed Income",
                    "ETFs",
                    "Mutual Funds",
                    "Cash",
                ],
                "Total": [8542, 3421, 1876, 987, 421],
                "Classified": [8487, 3398, 1876, 987, 421],
                "High Confidence": [8234, 3156, 1823, 945, 421],
                "Needs Review": [55, 23, 0, 0, 0],
                "Quality Score": ["99.4%", "99.3%", "100%", "100%", "100%"],
            },
        )

        issues_data = pd.DataFrame(
            {
                "Issue Type": [
                    "Missing ISIN",
                    "Duplicate Symbol",
                    "Classification Conflict",
                    "Data Inconsistency",
                ],
                "Severity": ["Medium", "Low", "High", "Medium"],
                "Count": [23, 8, 2, 12],
                "Institution": ["Mixed", "Wells Fargo", "Mixed", "AltoIRA"],
                "Last Detected": [
                    "2024-01-15",
                    "2024-01-14",
                    "2024-01-13",
                    "2024-01-15",
                ],
                "Status": ["Open", "Resolved", "Open", "In Progress"],
                "Action Required": [
                    "Manual ISIN lookup",
                    "None",
                    "Manual review",
                    "Data correction",
                ],
            },
        )

        # Sample quality trend chart
        fig = go.Figure()
        dates = pd.date_range(start="2024-01-01", end="2024-01-15", freq="D")
        quality_scores = [
            95 + 2 * np.sin(i / 7) + np.random.normal(0, 0.5) for i in range(len(dates))
        ]

        fig.add_trace(
            go.Scatter(x=dates, y=quality_scores, name="Overall Quality Score"),
        )
        fig.update_layout(
            title="Data Quality Trend",
            xaxis_title="Date",
            yaxis_title="Quality Score (%)",
        )

        return institution_data, security_data, issues_data, fig

    def _refresh_system_status(self):
        """Refresh system status information."""
        health_data = pd.DataFrame(
            {
                "Component": [
                    "Database",
                    "Redis Cache",
                    "API Server",
                    "Worker Queue",
                    "External APIs",
                ],
                "Status": [
                    "✅ Healthy",
                    "✅ Healthy",
                    "✅ Healthy",
                    "✅ Healthy",
                    "⚠️ Degraded",
                ],
                "Last Check": [
                    "2024-01-15 10:30",
                    "2024-01-15 10:30",
                    "2024-01-15 10:30",
                    "2024-01-15 10:29",
                    "2024-01-15 10:28",
                ],
                "Response Time": ["15ms", "2ms", "45ms", "N/A", "2.3s"],
                "Details": [
                    "200 connections",
                    "85% memory",
                    "4 workers",
                    "12 pending",
                    "Rate limited",
                ],
            },
        )

        service_data = pd.DataFrame(
            {
                "Service": [
                    "PostgreSQL",
                    "Redis",
                    "Security-Master API",
                    "Celery Worker",
                    "Prometheus",
                ],
                "Status": [
                    "✅ Running",
                    "✅ Running",
                    "✅ Running",
                    "✅ Running",
                    "✅ Running",
                ],
                "Uptime": ["15 days", "15 days", "7 days", "7 days", "15 days"],
                "Memory Usage": ["2.1 GB", "512 MB", "1.8 GB", "896 MB", "256 MB"],
                "CPU Usage": ["12%", "3%", "25%", "15%", "5%"],
                "Actions": ["Restart", "Restart", "Restart", "Restart", "Restart"],
            },
        )

        users_data = pd.DataFrame(
            {
                "Email": [
                    "admin@company.com",
                    "analyst@company.com",
                    "manager@company.com",
                ],
                "Name": ["System Admin", "Senior Analyst", "Portfolio Manager"],
                "Role": ["Admin", "Analyst", "Portfolio Manager"],
                "Last Login": [
                    "2024-01-15 09:15",
                    "2024-01-15 08:45",
                    "2024-01-14 16:30",
                ],
                "Session Status": ["Active", "Active", "Expired"],
                "Permissions": ["Full", "Read/Classify", "Read/Manage"],
            },
        )

        audit_data = pd.DataFrame(
            {
                "User": [
                    "admin@company.com",
                    "analyst@company.com",
                    "manager@company.com",
                ],
                "Action": [
                    "Export Generated",
                    "Classification Updated",
                    "Portfolio Created",
                ],
                "Resource": ["Client Portfolio", "AAPL Security", "Growth Portfolio"],
                "Timestamp": [
                    "2024-01-15 10:25",
                    "2024-01-15 09:30",
                    "2024-01-14 16:15",
                ],
                "IP Address": ["192.168.1.100", "192.168.1.101", "192.168.1.102"],
                "Result": ["Success", "Success", "Success"],
            },
        )

        api_data = pd.DataFrame(
            {
                "API": ["OpenFIGI", "Alpha Vantage", "Yahoo Finance"],
                "Requests Today": [1247, 456, 2341],
                "Rate Limit": ["25/min", "5/min", "2000/hr"],
                "Success Rate": ["98.5%", "96.2%", "99.8%"],
                "Avg Response Time": ["1.2s", "0.8s", "0.3s"],
                "Status": ["⚠️ Rate Limited", "✅ Healthy", "✅ Healthy"],
            },
        )

        return health_data, service_data, users_data, audit_data, api_data

    # Utility methods for styling and layout
    def _get_custom_css(self) -> str:
        """Get custom CSS styling for the application.

        Returns:
            str: CSS string with custom styling rules.
        """
        return """
        /* Security-Master Interface Styling */
        .gradio-container {
            max-width: 1600px !important;
            margin: auto !important;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        /* Header and branding */
        .sm-header {
            background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
            color: white;
            padding: 20px;
            margin: -20px -20px 20px -20px;
            border-radius: 0 0 12px 12px;
        }
        
        .sm-header h1 {
            margin: 0;
            font-size: 28px;
            font-weight: 600;
        }
        
        .sm-header p {
            margin: 5px 0 0 0;
            opacity: 0.9;
            font-size: 14px;
        }
        
        /* Statistics cards */
        .stats-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }
        
        .stat-card {
            background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            transition: transform 0.2s;
        }
        
        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        
        .stat-card h4 {
            margin: 0 0 10px 0;
            color: #64748b;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .stat-value {
            font-size: 24px;
            font-weight: 700;
            color: #1e293b;
        }
        
        /* Quality dashboard */
        .quality-dashboard {
            margin: 20px 0;
        }
        
        .quality-score-card {
            background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
            border: 2px solid #10b981;
            border-radius: 12px;
            padding: 25px;
            text-align: center;
        }
        
        .quality-score {
            font-size: 48px;
            font-weight: 800;
            color: #059669;
            margin: 10px 0;
        }
        
        .quality-trend {
            color: #065f46;
            font-weight: 500;
        }
        
        /* Tab styling */
        .tab-nav {
            background: linear-gradient(90deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 8px;
            padding: 4px;
            margin-bottom: 20px;
        }
        
        /* Status indicators */
        .status-success { color: #059669; font-weight: 600; }
        .status-warning { color: #d97706; font-weight: 600; }
        .status-error { color: #dc2626; font-weight: 600; }
        .status-info { color: #2563eb; font-weight: 600; }
        
        /* Form improvements */
        .gradio-textbox, .gradio-dropdown {
            border-radius: 6px !important;
            border: 1.5px solid #d1d5db !important;
        }
        
        .gradio-textbox:focus, .gradio-dropdown:focus {
            border-color: #3b82f6 !important;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
        }
        
        /* Button improvements */
        .gradio-button {
            border-radius: 6px !important;
            font-weight: 500 !important;
            transition: all 0.2s !important;
        }
        
        .gradio-button:hover {
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1) !important;
        }
        
        /* DataFrame styling */
        .gradio-dataframe table {
            border-collapse: collapse;
            width: 100%;
        }
        
        .gradio-dataframe th {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            padding: 12px 8px;
            font-weight: 600;
            color: #495057;
        }
        
        .gradio-dataframe td {
            border: 1px solid #dee2e6;
            padding: 10px 8px;
        }
        
        .gradio-dataframe tr:hover {
            background-color: #f8f9fa;
        }
        
        /* Footer styling */
        .sm-footer {
            margin-top: 40px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            text-align: center;
            color: #6c757d;
            font-size: 12px;
        }
        
        /* Responsive design */
        @media (max-width: 768px) {
            .gradio-container {
                max-width: 100% !important;
                margin: 0 !important;
                padding: 10px !important;
            }
            
            .stats-container {
                grid-template-columns: 1fr 1fr;
                gap: 10px;
            }
            
            .stat-card {
                padding: 15px;
            }
            
            .stat-value {
                font-size: 20px;
            }
        }
        
        /* Loading animations */
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .loading {
            animation: pulse 2s infinite;
        }
        """

    def _get_custom_head(self) -> str:
        """Get custom HTML head content.

        Returns:
            str: HTML string for insertion into the document head.
        """
        return """
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="description" content="Security-Master: Enterprise Portfolio Performance Security Classification System">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        """

    def _get_header_html(self) -> str:
        """Get header HTML content.

        Returns:
            str: HTML string for the application header.
        """
        return """
        <div class="sm-header">
            <h1>🏛️ Security-Master Enterprise System</h1>
            <p>Portfolio Performance Security Classification & Analytics Platform</p>
        </div>
        """

    def _get_footer_html(self) -> str:
        """Get footer HTML content.

        Returns:
            str: HTML string for the application footer.
        """
        return """
        <div class="sm-footer">
            Security-Master v5.0 | Enterprise Portfolio Performance System<br>
            Powered by PromptCraft UI Framework | Database: PostgreSQL 17 | Analytics: Python/Pandas
        </div>
        """


def create_security_master_app() -> gr.Blocks:
    """
    Factory function to create the Security-Master Gradio application.

    Returns:
        gr.Blocks: The complete Security-Master web application
    """
    interface = SecurityMasterInterface()
    app = interface.create_app()

    logger.info("Security-Master Gradio application created successfully")
    return app


def launch_security_master_app(
    server_name: str = "0.0.0.0",
    server_port: int = 7860,
    share: bool = False,
    auth: callable | None = None,
    show_error: bool = True,
    debug: bool = False,
) -> None:
    """
    Launch the Security-Master web application.

    Args:
        server_name: Server hostname (default: 0.0.0.0 for Docker)
        server_port: Server port (default: 7860)
        share: Whether to create public sharing link
        auth: Authentication function (handled by Cloudflare Access)
        show_error: Whether to show error messages
        debug: Enable debug mode
    """
    app = create_security_master_app()

    logger.info(f"Launching Security-Master application on {server_name}:{server_port}")

    app.launch(
        server_name=server_name,
        server_port=server_port,
        share=share,
        auth=auth,  # Authentication handled by Cloudflare Access middleware
        show_error=show_error,
        debug=debug,
        favicon_path=None,  # Could add custom favicon
        ssl_verify=False,  # SSL handled by Cloudflare tunnel
        quiet=not debug,
    )


if __name__ == "__main__":
    # Launch the application in standalone mode
    launch_security_master_app(debug=True)
