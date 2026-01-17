# Portfolio Screener Application Roadmap

> **Vision**: Desktop portfolio screening application powered by PySFT for discovering, analyzing, and tracking securities across US, global, and TASE markets with AI-powered insights.

## 📊 Project Overview

**PySFT Core Capabilities:**
- Static data fetching (price, expense ratios, dividends, etc...) using yfinance + custom TASE scrapers
- Fundamental data (statements, ratios, metrics)
- LLM-powered analysis (portfolio insights, security research, risk assessment, market commentary)
- Data intelligence (normalization, validation, caching, multi-source aggregation)

**Application Goals:**
- Desktop-first MVP with advanced screening
- Portfolio tracking and analysis
- AI-powered insights via PySFT agents

## 🎯 Development Phases

### **Phase 0: Repository Setup & Quality Assurance** ✓ IN PROGRESS

> Establish testing infrastructure, CI/CD, and governance before external contributions

**Key Deliverables:**
- [ ] Testing infrastructure (pytest, integration/e2e tests)
- [ ] Code quality tools (Black, Pylint, isort, mypy, pre-commit hooks)
- [ ] CI/CD pipelines (test, lint, security, docs workflows on GitHub Actions)
- [ ] Branch protection (require PR reviews, passing tests, coverage maintenance)
- [ ] Documentation (CONTRIBUTING.md, CODE_OF_CONDUCT.md, issue/PR templates)
- [ ] Initial test suite (all core modules, integration tests, fixtures)

---

### **Phase 1: Foundation & Core Data Layer**

> **Goal**:  Establish robust backend infrastructure with PySFT integration

#### 1.1 PySFT Enhancement & Integration

- [ ] **Expand PySFT Capabilities**
  - Implement fundamental data fetching (P/E, market cap, sector, etc.)
  - Add batch fetching optimization for large-scale screening
  - Enhance error handling and retry logic
  - Implement data quality validation
  - Create comprehensive API for screener consumption

- [ ] **Testing for New Features** (Required for each item above)
  - Unit tests for fundamental data fetching
  - Integration tests for batch operations
  - Error handling test scenarios
  - Data validation test cases
  - API contract tests

- [ ] **Performance Testing**
  - Benchmark single security fetch
  - Benchmark batch fetching (up to a test case of around 500 indicators)
  - Test cache effectiveness
  - Identify and optimize bottlenecks

#### 1.2 Backend API Development

- [ ] **API Framework Setup**
  - Choose Python web framework (FastAPI recommended)
  - Design RESTful API endpoints
  - Implement request/response models
  - Add authentication mechanism (JWT tokens)
  - Set up API documentation (OpenAPI/Swagger)

- [ ] **API Testing**
  - Unit tests for all endpoints
  - Integration tests for API workflows
  - Authentication/authorization tests
  - API contract testing
  - Load testing with locust or similar

- [ ] **Core API Endpoints**
  - `/screen` - Execute screening with filters
  - `/securities/{symbol}` - Get detailed security data
  - `/portfolio` - Portfolio management CRUD
  - `/watchlist` - Watchlist management
  - `/filters` - Save/load filter templates
  - `/insights/{symbol}` - Get AI-powered insights (powered by PySFT agents)
  - `/insights/portfolio/{id}` - Get portfolio-level insights

- [ ] **Error Handling & Logging**
  - Structured logging (leverage PySFT's logger)
  - Centralized error handling
  - Request tracing and monitoring

#### 1.3 Database Design & Implementation

- [ ] **Database Selection**
  - Evaluate options: PostgreSQL, SQLite, MySQL and more
  - Consider:  query complexity, scalability, desktop deployment
  - Decision criteria: lightweight for desktop, good Python support

- [ ] **Schema Design**
  - User profiles and authentication
  - Portfolio holdings and transactions
  - Watchlists and screening templates
  - Security metadata cache
  - Historical screening results
  - **LLM insights cache** (store generated insights with timestamps)
  - **LLM usage tracking** (API calls, tokens, costs)

- [ ] **Database Testing**
  - Unit tests for models and queries
  - Integration tests for CRUD operations
  - Test data migrations
  - Test database constraints and indexes
  - Performance testing for complex queries

- [ ] **Database Migrations**
  - Set up migration framework (Alembic for Python)
  - Version control for schema changes
  - Seed data for development/testing

---

### **Phase 2: LLM Agent Foundation (PySFT)**

> **Goal**: Build the LLM agent infrastructure within PySFT for intelligent analysis

#### 2.1 LLM Integration Architecture

- [ ] **LLM Provider Setup**
  - Choose primary LLM provider(s): OpenAI, Anthropic, local models (Ollama, LM Studio)
  - Support multiple providers with fallback strategy
  - Implement provider abstraction layer
  - Configure API key management (environment variables, secrets)
  - Set up rate limiting and quota management

- [ ] **Agent Framework Design**
  - Design agent architecture (ReAct, Chain-of-Thought, etc.)
  - Implement prompt templates for different analysis types
  - Create context management system (conversation history, data context)
  - Build tool-calling infrastructure (function calling)
  - Implement agent memory and state management

- [ ] **Testing LLM Integration**
  - Mock LLM responses for deterministic testing
  - Test API error handling (rate limits, timeouts, invalid keys)
  - Test provider fallback mechanisms
  - Test prompt templating and formatting
  - Validate output parsing and structure

#### 2.2 Core LLM Agents

- [ ] **Security Analysis Agent**
  - Analyze individual securities with fetched data
  - Generate investment thesis and summary
  - Identify key metrics and trends
  - Compare to sector/industry peers
  - Access web for latest news/developments
  - Tools: web search, data fetching, calculation

- [ ] **Portfolio Analysis Agent**
  - Analyze portfolio composition and allocation
  - Identify diversification opportunities
  - Assess overall risk profile
  - Generate performance commentary
  - Suggest rebalancing strategies
  - Tools:  portfolio data access, calculations, benchmarking

- [ ] **Market Research Agent**
  - Conduct web research for securities
  - Aggregate news and sentiment
  - Identify relevant SEC filings or announcements
  - Summarize analyst opinions
  - Track corporate actions (dividends, splits, etc.)
  - Tools: web search, news APIs, SEC EDGAR access

- [ ] **Risk Assessment Agent**
  - Evaluate security-specific risks
  - Analyze portfolio risk factors
  - Identify concentration risks
  - Assess correlation and volatility
  - Provide risk mitigation suggestions
  - Tools: statistical analysis, historical data, VaR calculations

- [ ] **Comparative Analysis Agent**
  - Compare multiple securities side-by-side
  - Identify relative strengths/weaknesses
  - Generate ranking and scoring
  - Explain valuation differences
  - Tools: data fetching, calculations, statistical analysis

#### 2.3 Agent Tools & Capabilities

- [ ] **Data Fetching Tools**
  - Fetch current and historical price data
  - Fetch fundamental data (P/E, revenue, etc.)
  - Fetch corporate actions and events
  - Access cached data efficiently

- [ ] **Web Research Tools**
  - Web search integration (Google, Bing, Brave Search)
  - News API integration
  - SEC EDGAR filing access
  - Social media sentiment (optional)
  - Web scraping for specific sources

- [ ] **Calculation Tools**
  - Financial ratio calculations
  - Return and performance metrics
  - Risk metrics (volatility, Sharpe, etc.)
  - Statistical analysis
  - Correlation and covariance

- [ ] **Context Management**
  - Maintain conversation history
  - Track user preferences and goals
  - Remember previous analyses
  - Build knowledge graph of securities

#### 2.4 LLM Agent Testing

- [ ] **Unit Testing**
  - Test prompt generation
  - Test output parsing
  - Test tool invocation
  - Mock LLM responses for consistency

- [ ] **Integration Testing**
  - Test end-to-end agent workflows
  - Test tool execution and data fetching
  - Test web research capabilities
  - Validate generated insights quality

- [ ] **Quality Assurance**
  - Implement output quality scoring
  - Track hallucination detection
  - Validate factual accuracy
  - Test edge cases and error handling
### **Phase 1: Foundation & Core Data Layer**

> Establish backend infrastructure with PySFT integration

**Key Deliverables:**
- [ ] PySFT enhancements (fundamental data, batch fetching, error handling, validation)
- [ ] Backend API (FastAPI, RESTful endpoints, authentication, OpenAPI docs)
- [ ] Core endpoints (`/screen`, `/securities`, `/portfolio`, `/watchlist`, `/insights`)
- [ ] Database (schema design, migrations, user/portfolio/insights/LLM usage tracking)
- [ ] Comprehensive testing (all features require unit + integration tests)n
  - Price charts (historical data)
  - Fundamental metrics display
  - **AI-Generated Insights Section** (powered by PySFT agents)
  - Related securities suggestions

#### 3.3 Portfolio Management

- [ ] **Portfolio CRUD**
  - Create/edit/delete portfolios
  - Add/remove holdings
  - Transaction history
  - Cost basis tracking

- [ ] **Testing**
  - Unit tests for portfolio logic
  - Integration tests for portfolio API
  - Widget tests for portfolio UI
  - Test transaction calculations

- [ ] **Portfolio Analytics**
  - Total value and P&L calculation
  - Asset allocation visualization
  - Performance metrics (returns, volatility)
  - Comparison vs.  benchmarks
  - **AI-Generated Portfolio Insights** (powered by PySFT agents)

- [ ] **Watchlist Management**
  - Multiple watchlists support
  - Real-time price updates
  - Price alerts configuration
  - Bulk operations

---

### **Phase 4: AI Insights Integration**

> **Goal**: Expose PySFT LLM agents to the desktop application

#### 4.1 Insights UI Components

- [ ] **Security Insights Panel**
  - Display AI-generated security analysis
  - Show investment thesis and key points
  - Display risk factors and opportunities
  - Show comparative analysis vs. peers
  - Refresh/regenerate insights on demand
  - Timestamp and cache indicators

- [ ] **Portfolio Insights Dashboard**
  - Display overall portfolio analysis
  - Show allocation recommendations
  - Display risk assessment
  - Show diversification suggestions
  - Performance commentary
  - Actionable recommendations

- [ ] **Insights History**
  - Track previously generated insights
  - Compare insights over time
  - Bookmark important insights
  - Export insights to PDF/markdown

- [ ] **Interactive Chat Interface (Optional)**
  - Chat with AI about specific securities
  - Ask custom questions about portfolio
  - Natural language queries
  - Conversation history

#### 4.2 Insights Configuration

- [ ] **User Preferences**
  - Choose LLM provider preference
  - Configure insight verbosity
  - Set refresh frequency
  - Enable/disable specific agents
  - Configure web research depth
### **Phase 2: LLM Agent Foundation (PySFT)**

> Build LLM agent infrastructure for intelligent analysis

**Key Deliverables:**
- [ ] LLM integration (OpenAI/Anthropic/local models, provider abstraction, API key management)
- [ ] Agent framework (ReAct/CoT architecture, prompt templates, tool-calling, context management)
- [ ] Core agents (Security Analysis, Portfolio Analysis, Market Research, Risk Assessment, Comparative Analysis)
- [ ] Agent tools (data fetching, web research, calculations, SEC EDGAR access)
- [ ] Testing (mock LLM responses, quality validation, token tracking)
- [ ] Prompt optimization (library, versioning, A/B testing, caching)
#### 6.2 Personalization & Learning

- [ ] **User Profile Learning**
  - Learn user investment preferences
  - Adapt recommendations to user style
  - Track successful vs. unsuccessful insights
  - Personalized risk tolerance

- [ ] **Feedback Loop**
  - Use user feedback to improve prompts
  - Track insight quality metrics
  - A/B test prompt variations
  - Continuous improvement pipeline

#### 6.3 Advanced Analysis

- [ ] **Scenario Analysis**
  - "What-if" portfolio scenarios
  - Stress testing
  - Economic scenario modeling
  - Impact analysis

- [ ] **Predictive Insights**
  - Trend forecasting (with disclaimers)
  - Pattern-based predictions
  - Risk probability estimates
  - Confidence intervals

#### 6.4 Knowledge Graph

- [ ] **Entity Relationships**
  - Build knowledge graph of securities
  - Track relationships (competitors, suppliers, etc.)
  - Industry connections
  - Cross-holdings and correlations

- [ ] **Historical Knowledge**
  - Track previous analyses
  - Remember past recommendations
  - Track outcome of suggestions
  - Build institutional knowledge

---

### **Phase 7: User Experience Enhancements**

> **Goal**:  Polish UI/UX, add productivity features

#### 7.1 Advanced UI Features

- [ ] **Customization**
  - Customizable dashboard layouts
  - Save workspace preferences
  - Theme customization (light/dark modes)
  - Keyboard shortcuts

- [ ] **Testing**
  - Test theme switching
  - Test preference persistence
  - Test keyboard shortcuts
  - Test accessibility features

- [ ] **Visualization Enhancements**
  - Interactive charts with zoom/pan
  - Heatmaps (correlation, performance)
  - Scatter plots (risk-return profiles)
  - Distribution histograms

- [ ] **Data Export & Reporting**
  - PDF report generation (with AI insights)
  - Custom report templates
  - Scheduled reports
  - Email integration

#### 7.2 Collaboration Features

- [ ] **Screen Sharing**
  - Export screens as shareable links/files
  - Import community screens
  - Screen marketplace (optional)

- [ ] **Notes & Annotations**
  - Add notes to securities
  - Tag and categorize holdings
  - Research journal
  - Integrate AI insights with notes

---

### **Phase 8: Performance & Scalability**

> **Goal**:  Optimize for speed, reliability, and large-scale data handling

#### 8.1 Performance Optimization

- [ ] **Data Fetching Optimization**
  - Parallel fetching for multiple securities
  - Request batching and deduplication
  - Connection pooling
### **Phase 5: Advanced Screening & Analytics**

> Sophisticated screening and analysis tools

**Key Deliverables:**
- [ ] Enhanced filtering (nested groups, operators, percentiles, cross-security comparisons)
- [ ] AI-powered screening (natural language screen creation, AI-suggested screens, result explanations)
- [ ] Sector/industry analysis (classification, peer comparison, heatmaps, AI commentary)
- [ ] TASE features (dual-listed detection, symbol mapping, ILS/USD conversion, indices)
- [ ] Historical analysis (time-series screening, backtesting, AI analysis of results)
- [ ] Technical analysis (candlestick charts, indicators, pattern recognition, AI insights)
- [ ] Performance analytics (returns, benchmarks, risk metrics, AI commentary)hed data
- **Application Stability**: < 1% crash rate
- **LLM Latency**: < 10s for standard insights, < 30s for deep research

---

## 🚀 Immediate Next Steps

### Sprint 1: Testing Infrastructure (CRITICAL - Before Public Release)
1. ✅ Set up pytest framework and test directory structure
2. ✅ Configure test coverage reporting (Codecov/Coveralls)
3. ✅ Write unit tests for all existing PySFT modules (80%+ coverage goal)
4. ✅ Create integration tests for data fetching workflows
5. ✅ Set up test fixtures and mock data
6. ✅ Document testing strategy and guidelines

### Sprint 2: Code Quality & CI/CD
1. ✅ Configure Black, Pylint, isort, mypy
2. ✅ Set up pre-commit hooks
3. ✅ Create GitHub Actions workflows (test, lint, security)
4. ✅ Configure required status checks
5. ✅ Set up code coverage tracking
6. ✅ Add quality badges to README

### Sprint 3: Repository Governance
1. ✅ Set up branch protection on `main` branch
2. ✅ Create CONTRIBUTING.md with testing requirements
3. ✅ Add PR and issue templates
4. ✅ Create CODEOWNERS file
5. ✅ Add CODE_OF_CONDUCT.md
6. ✅ Document code review standards

### Sprint 4: PySFT Enhancement
1. Design fundamental data fetching API (with tests)
2. Implement batch fetching for screening (with tests)
3. Add comprehensive error handling (with tests)
4. Write performance benchmarks
5. Document API for screener consumption

### Sprint 5: LLM Agent Foundation
1. Choose and set up LLM provider(s)
2. Design agent architecture and prompt templates
3. Implement Security Analysis Agent (with mocked tests)
4. Create tool infrastructure for web research
5. Set up LLM response caching

### Sprint 6: LLM Agent Testing & Expansion
1. Write comprehensive tests for LLM integration
### **Phase 4: AI Insights Integration**

> Expose PySFT LLM agents to desktop application

**Key Deliverables:**
- [ ] Insights UI (security/portfolio panels, history tracking, PDF export, optional chat interface)
- [ ] Configuration (LLM provider selection, verbosity, refresh frequency, agent toggles)
- [ ] Cost management (token tracking, budgets, quality vs cost modes)
- [ ] Quality & feedback (confidence scores, source attribution, user ratings, inaccuracy reporting)
- [ ] Testing (widget tests, integration tests, error handling, caching validation)de tests (85%+ coverage)
- **Bug fixes**: Must include regression tests
- **Refactoring**:  Maintain or improve existing coverage
- **PRs**: Cannot decrease overall coverage
- **LLM features**: Must have mocked tests + manual quality validation

---

## 🤖 LLM Agent Design Principles

### **Phase 6: Advanced AI Features**

> Enhance LLM agents with advanced capabilities

**Key Deliverables:**
- [ ] Multi-agent orchestration (coordinated workflows, agent communication, parallel execution)
- [ ] Autonomous research (proactive monitoring, scheduled analysis, alerts)
- [ ] Personalization (user preference learning, adapted recommendations, risk tolerance tracking)
- [ ] Advanced analysis (scenario modeling, stress testing, predictive insights with disclaimers)
- [ ] Knowledge graph (entity relationships, industry connections, historical knowledge, outcome tracking)### **Phase 7: User Experience Enhancements**

> Polish UI/UX and add productivity features

**Key Deliverables:**
- [ ] Customization (dashboard layouts, themes, keyboard shortcuts, workspace preferences)
- [ ] Visualization (interactive charts, heatmaps, scatter plots, histograms)
- [ ] Reporting (PDF generation with AI insights, templates, scheduled reports, email)
- [ ] Collaboration (screen sharing/import, community screens, marketplace)
- [ ] Notes & annotations (security notes, tags, research journal, AI insight integration)### **Phase 8: Performance & Scalability**

> Optimize for speed, reliability, and scale

**Key Deliverables:**
- [ ] Data fetching optimization (parallel fetching, batching, connection pooling, rate limiting)
- [ ] LLM optimization (aggressive caching, batch generation, streaming, token efficiency)
- [ ] UI performance (virtual scrolling, lazy loading, debouncing, memory management)
- [ ] Caching enhancements (multi-level, smart warming, analytics, TTL)
- [ ] Error recovery (graceful degradation, offline mode, retries, LLM fallbacks)
- [ ] Reliability testing (chaos engineering, failure scenarios, data corruption handling)
- [ ] Data integrity (validation, consistency checks, backup/restore)## 🏗️ Technical Stack

**Backend (PySFT):** Python, yfinance, TASE scrapers, FastAPI, PostgreSQL/SQLite, Redis/SQLite caching  
**LLM:** OpenAI GPT-4/Anthropic Claude (primary), Ollama/LM Studio (local), LangChain/LlamaIndex, Tavily/Brave Search  
**Frontend:** Flutter (Dart), Riverpod, Dio, fl_chart, flutter_markdown  
**Testing:** pytest, flutter_test, Black/Pylint/mypy, Codecov, GitHub Actions  
**Infrastructure:** Git/GitHub, GitHub Actions CI/CD, environment secrets, LLM usage tracking

**Out of Scope:** ❌ Brokerage integrations ❌ Mobile apps ❌ Web app ❌ Social trading ❌ Automated trading## 🎯 Success Metrics

**Development:** Testing 80%+, CI/CD functional, repo configured, PySFT with fundamentals, 3+ LLM agents, MVP released, 10+ contributors  
**Quality:** 80%+ coverage (90%+ core), 99%+ test pass rate, 95%+ build success, A/B code quality grade  
**AI Quality:** 90%+ insight accuracy, 4+ star satisfaction, <10s response time, 70%+ cache hit rate, <5000 tokens/insight  
**Performance:** <5s screen execution (5K securities), 60 FPS UI, 99.9% data accuracy, <1% crash rate, <10s/30s LLM latency## 🚀 Immediate Next Steps

**Sprint 1-3 (Phase 0):** ✅ Testing infrastructure, CI/CD, repository governance  
**Sprint 4:** PySFT enhancement (fundamentals API, batch fetching, error handling, benchmarks)  
**Sprint 5-6:** LLM agents (provider setup, architecture, Security/Portfolio/Research agents, tools, testing, optimization)  
**Sprint 7:** Backend API (FastAPI, database schema, endpoints, authentication, docs)  
**Sprint 8:** Flutter MVP (project init, state management, screening UI, API integration, insights panel)## 📚 Documentation

**Contributors:** README ✅, CONTRIBUTING.md, CODE_OF_CONDUCT.md, ROADMAP ✅, ARCHITECTURE, DEVELOPMENT, TESTING, CODE_QUALITY, LLM_AGENTS  
**Users (Post-MVP):** User Guide, AI Insights Guide, FAQ, Troubleshooting, Video Tutorials  
**Developers:** API docs (OpenAPI), PySFT Integration, Database Schema, Deployment, Testing Best Practices, LLM Agent Development, Prompt Engineering

## 🧪 Testing & AI Principles

**Testing Philosophy:** TDD when appropriate, test behavior not implementation, mock external dependencies, 85%+ coverage for new features, maintain fast execution, LLM response mocking + quality validation

**LLM Agent Philosophy:** Transparency (show sources), accuracy first, user control, cost awareness, privacy protection, graceful fallbacks, prompt versioning, A/B testing, structured outputs, fact-checking## 🤝 Contributing

⚠️ **Currently in Phase 0** - establishing testing/quality standards before external contributions.  
**Ready when:** Testing 80%+, CI/CD functional, CONTRIBUTING.md published, branch protection configured

**Get Involved (Soon):** Check CONTRIBUTING.md, browse "good first issue" tasks, join GitHub Discussions, submit proposals  
**Note:** All contributions require @LuciosProjects approval

## 📞 Resources

**Repository:** [LuciosProjects/PySFT](https://github.com/LuciosProjects/PySFT) | **Issues/Discussions:** GitHub | **Maintainer:** @LuciosProjects

---
*Last Updated: 2025-12-20 | Version: 5.0 (Concise) | 