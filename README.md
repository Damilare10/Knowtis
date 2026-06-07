Knowtis — Updated Product Requirements Document (PRD)
1. Product Overview
Product Name
Knowtis
Vision
An AI-powered academic communication assistant that helps students stay informed by filtering noisy university WhatsApp groups and surfacing only relevant, actionable academic updates in real time.
Mission
To reduce information overload for students by acting as a lean, highly focused reminder and notification engine for university life.
2. Problem Statement
University WhatsApp groups are flooded with:
• casual conversations,
• repeated questions,
• memes,
• fragmented announcements,
• forwarded duplicate messages.
As a result, students frequently miss:
• assignment deadlines,
• class cancellations,
• timetable changes,
• quizzes and exams,
• urgent lecturer instructions.
Knowtis solves this by extracting, categorizing, deduplicating, and delivering time-sensitive academic events while intentionally ignoring unnecessary media and group noise.
3. Product Identity
Knowtis is NOT:
• a Learning Management System (LMS),
• a note-sharing platform,
• a PDF storage system,
• or a class discussion platform.
Knowtis is:
• an AI-powered academic signal extraction engine,
• focused strictly on reminders, schedules, deadlines, and actionable academic updates.
4. Core Objectives
Primary Goals
• Reduce academic information overload.
• Extract actionable academic events accurately.
• Surface important updates in real time.
• Minimize onboarding friction.
• Maintain a calm, organized student experience.
Success Metrics
• Message classification accuracy > 90%
• OCR extraction accuracy
• Event extraction success rate
• Notification open rate
• Daily Active Users (DAU)
• Reduced duplicate alerts
• Student retention after 30 days
5. System Architecture
Architecture Style
Centralized multi-tenant architecture.
Backend Stack
• FastAPI (Python)
• PostgreSQL
• Redis
• Dockerized worker services
Database
PostgreSQL with:
• Row-Level Security (RLS)
• pgvector extension
• encrypted storage
Purpose:
• semantic deduplication,
• vector similarity search,
• future AI memory expansion.
Queueing & Workers
• Redis + BullMQ (or Celery)
• asynchronous join queues,
• OCR processing workers,
• AI classification workers,
• notification workers.
Infrastructure
• Dockerized microservices
• Single VPS deployment for MVP
• Horizontal scaling later via worker replication
5.9 AI Retrieval & Response Architecture
Overview
Knowtis uses a hybrid AI architecture designed around:
• semantic retrieval,
• structured academic event storage,
• deterministic response generation,
• and optional conversational AI enhancement.
The platform prioritizes reliability, low latency, and low operational cost over fully generative AI behavior.
Core AI Philosophy
Knowtis is not designed as a general-purpose chatbot.
Instead, the AI system focuses on:
• retrieving academic information,
• prioritizing urgency,
• summarizing updates,
• and helping students quickly understand what matters most.
Semantic Retrieval Layer
The platform uses MiniLM embeddings with pgvector semantic search for:
• message understanding,
• event similarity matching,
• OCR instruction interpretation,
• semantic deduplication,
• and academic query retrieval.
MiniLM enables flexible understanding of student phrasing without requiring a large language model for every interaction.
Structured Academic Memory
Extracted events are stored as structured academic objects within PostgreSQL.
Example fields:
• event type,
• course code,
• urgency level,
• deadline,
• venue,
• reminder state,
• and semantic embedding vectors.
This allows reliable querying and low-hallucination responses.
Deterministic Response Engine (Free Tier)
Most student queries are handled without a large language model.
The free-tier AI experience uses:
• semantic intent detection,
• structured database retrieval,
• and template-based response formatting.
Example queries:
• “What’s due tomorrow?”
• “Any class cancellations?”
• “Show upcoming exams”
Responses are generated deterministically for:
• speed,
• reliability,
• low latency,
• and reduced operational cost.
Conversational AI Layer (Premium Tier)
Premium users gain access to conversational AI enhancement powered by lightweight external inference models.
Capabilities include:
• contextual summaries,
• follow-up questions,
• prioritization assistance,
• natural-language schedule explanations,
• and conversational academic querying.
The conversational layer operates on retrieved academic context rather than unrestricted internet knowledge.
Hybrid Retrieval Pipeline
User Query ↓ Intent Understanding ↓ MiniLM Semantic Retrieval ↓ Relevant Academic Context Retrieved ↓ Response Formatter OR Conversational AI Layer ↓ Final Response
External AI Inference Strategy
Knowtis may use lightweight inference APIs (such as Groq-hosted models) for premium conversational responses.
The external AI layer is used only for:
• natural-language generation,
• contextual summaries,
• and conversational refinement.
Core academic logic remains local and deterministic.
Reliability & Cost Optimization
The system is intentionally designed so that:
• reminders,
• retrieval,
• OCR,
• dashboards,
• and event tracking
continue functioning even if external AI services are unavailable.
This ensures graceful degradation and predictable operating costs.
Design Principle
Knowtis treats AI as an enhancement layer over structured academic intelligence rather than the foundation of the platform itself.

6. Core Functional Requirements
6.1 Zero-Friction WhatsApp Integration ("Paste & Go")
Features
• Headless WhatsApp listeners
• Invite-link validation
• Automatic group joining
• Session persistence
• Auto-reconnect handling
User Flow
• Student copies a WhatsApp invite link.
• Student pastes the link into Knowtis.
• Queue validates and schedules the join.
• Knowtis listener joins automatically.
• Group monitoring begins.
Anti-Ban Protection
• staggered 3-minute join intervals,
• asynchronous queueing,
• session rotation,
• randomized worker timing,
• listener load balancing.
6.2 NLP Message Intelligence (Signal vs. Noise)
AI Pipeline
Incoming messages pass through:
• preprocessing,
• classification,
• event extraction,
• semantic deduplication,
• reminder generation.
Classification Categories
• Assignments
• Exams/Quizzes
• Timetable Changes
• Class Cancellations
• Lecturer Announcements
AI Stack
MVP
• MiniLM semantic embedding pipeline
Confidence Scoring
Each event receives:
• relevance score,
• confidence score,
• urgency score.
Low-confidence messages are ignored or flagged.
6.3 Semantic Deduplication
Purpose
Prevent repeated alerts when the same notice is forwarded multiple times.
Implementation
• Vector embeddings stored in pgvector.
• New events compared against existing academic events.
• Similar events collapse into a single canonical notification.
Example
10 forwarded: "ELE 310 test moved to Thursday"
→ becomes: 1 unified event notification.
6.4 Memory & Event Extraction
Structured Extraction
Converts raw text into structured academic objects.
Example:
Input: "ELE 310 quiz tomorrow by 10am"
Output:
• Event: Quiz
• Course: ELE 310
• Date: Tomorrow
• Time: 10:00 AM
Fact Compression
SimpleMem maintains:
• active deadlines,
• upcoming schedules,
• unresolved reminders,
• recurring timetable events.
6.5 On-Demand OCR Extraction (PaddleOCR)
Design Philosophy
Knowtis ignores unnecessary media by default.
No PDFs, videos, or files are permanently stored.
OCR Trigger Flow
• Student replies to an image.
• Student tags the bot: "@Knowtis extract"
• The image is fetched temporarily.
• PaddleOCR extracts the text.
• The extracted text enters the AI event pipeline.
• Structured events are created automatically.
OCR Targets
• Timetables
• Exam schedules
• Venue notices
• Assignment posters
• Department flyers
OCR Stack
• PaddleOCR
• OpenCV preprocessing
OCR Output Goals
Extract:
• dates,
• venues,
• course codes,
• times,
• structured schedules.
Not just raw text.
6.5.1 Smart OCR Querying & Selective Extraction
Overview
Knowtis supports instruction-aware OCR extraction for academic images such as:
• exam timetables,
• course schedules,
• departmental notices,
• assignment lists,
• and venue charts.
After OCR extraction, students can apply natural-language filters to extract only the information relevant to them.
Example User Commands
Students may reply to an image and tag the bot with instructions such as:
• "@Knowtis extract only 300-level courses"
• "@Knowtis save only ELE courses"
• "@Knowtis ignore GST exams"
• "@Knowtis extract exams happening this week"
• "@Knowtis save only my department timetable"
Processing Pipeline
Image ↓ PaddleOCR Extraction ↓ Layout & Table Parsing ↓ Structured Academic Data ↓ Natural Language Instruction Parsing ↓ Rule/Intent Filtering ↓ Filtered Event Generation ↓ Dashboard + Reminder Creation
Structured OCR Parsing
The OCR pipeline does not store raw extracted text alone.
Instead, timetable and notice data are converted into structured academic objects.
Example:
Input: "ELE 310 — June 12 — 10:00 AM — Hall B"
Structured Output:
• Course Code: ELE 310
• Course Level: 300
• Date: June 12
• Time: 10:00 AM
• Venue: Hall B
This enables:
• filtering,
• semantic querying,
• reminder generation,
• and calendar synchronization.
Semantic Instruction Understanding
Natural-language instructions are interpreted using:
• MiniLM semantic embeddings,
• lightweight intent matching,
• and rule-based filtering.
Example:
The following commands are treated similarly:
• "extract courses starting with 3"
• "only 300-level courses"
• "show only year 3 exams"
Supported Filter Types (Initial MVP)
Course-Level Filtering
Examples:
• 100-level
• 200-level
• 300-level
Department Filtering
Examples:
• ELE
• CSC
• MEE
Date Filtering
Examples:
• "this week"
• "tomorrow"
• "Monday only"
Exclusion Rules
Examples:
• ignore GST courses
• exclude practicals
Smart Reminder Generation
Filtered timetable entries can automatically:
• create reminders,
• generate sticky notes,
• appear in the Night Brief,
• and sync to external calendars.
Design Philosophy
Knowtis aims to extract only the information relevant to the student rather than overwhelming them with entire timetable dumps.
This preserves:
• clarity,
• personalization,
• and low cognitive load.
Future Expansion
Potential future upgrades:
• automatic department detection,
• user-specific timetable profiles,
• timetable conflict detection,
• personalized academic schedule generation,
• OCR-powered smart calendar construction.

6.6 User Dashboard ("The Cascade UI")
Design Identity
The dashboard uses a calm pastel-based "Sticky Note Cascade" interface.
Purpose:
• reduce cognitive overload,
• improve deadline visibility,
• create visual urgency without stress.
Dashboard Features
• cascading sticky-note reminders,
• realtime academic event feed,
• categorized updates,
• upcoming timeline,
• notification inbox.
Sticky Note Priority Colors
Deadline Soon
Soft coral: #FFB3A7
Upcoming
Pastel yellow: #FFF3B0
Low Urgency
Mint green: #B8F0D4
Informational
Lavender: #D4C5F9
Core UI Palette
Primary
#4F46E5
Accent CTA
#6366F1
Background
#F8F7FF
Text
#1E1B2E
Frontend Stack
• Next.js
• TailwindCSS
• WebSockets
6.7 AI Catch-Up Agent
Purpose
A lightweight academic query assistant.
The agent ONLY answers:
• extracted academic events,
• reminders,
• schedules,
• deadlines,
• known notices.
Example Queries
• "What’s due tomorrow?"
• "Any ELE 310 updates?"
• "When is the next quiz?"
Free Tier
Predefined quick-action chips only.
Premium Tier
Natural language conversational queries.
6.8 Notification Engine
Delivery Channels
• In-app direct messages
• WhatsApp direct alerts
• Push notifications
No email notifications.
Night Brief
Every evening:
• summarized upcoming events,
• tomorrow’s deadlines,
• urgent changes,
• pending reminders.
Delivered directly into the user's Knowtis inbox.
Premium Alerts
Premium users receive:
• instant timeline-shift notifications,
• urgent lecturer alerts,
• realtime cancellation notices.
6.9 Calendar Integration
One-Click Sync
Users can sync:
• assignments,
• exams,
• quizzes,
• schedules
directly to:
• Google Calendar
• Outlook Calendar
7. Authentication & Access Control
Login Methods
• Google OAuth
• Email/password authentication
Roles
Student
• links groups,
• receives updates,
• manages reminders.
System Admin
• monitors infrastructure,
• manages queues,
• tracks AI performance,
• oversees moderation.
No Group Admin role exists.
8. Data Privacy & Security
Data Minimization
• Messages processed in memory.
• Media ignored unless explicitly tagged.
• Only extracted academic events persist long-term.
Security
• encrypted database storage,
• secure OAuth token handling,
• secure session management.
User Consent
Clear onboarding disclosure explaining:
• how WhatsApp groups are monitored,
• what data is stored,
• what media is ignored.
9. Monetization Strategy
FeatureFree TierPremium TierGroup LimitsMax 2 groupsUnlimitedCascade NotesTop 3 eventsTop 5 + source linksNotification SpeedNight Brief onlyInstant alertsAI AgentQuick-action chipsFull conversational modeCalendar SyncDisabledOne-click sync 
10. Development Roadmap
Phase 1 — Infrastructure & Auth (Weeks 1–2)
• VPS setup
• PostgreSQL + pgvector
• authentication system
• queue infrastructure
Phase 2 — WhatsApp & AI Pipeline (Weeks 3–4)
• Puppeteer workers
• fastText classifier
• confidence scoring
• event extraction pipeline
Phase 3 — OCR & Intelligence (Weeks 5–6)
• PaddleOCR integration
• OpenCV preprocessing
• semantic deduplication
• premium tier logic
Phase 4 — Frontend & Launch (Weeks 7–8)
• Cascade dashboard UI
• realtime feed
• notification inbox
• end-to-end testing
• MVP deployment
11. Future Expansion
Potential Future Features
• native mobile apps,
• AI study planner,
• timetable auto-generation,
• lecturer dashboards,
• smart academic analytics,
• voice-based catch-up summaries.

6.10 Reliability, Coverage Integrity & Graceful Degradation
Design Philosophy
Knowtis is designed as a resilient academic communication layer, not merely a WhatsApp bot.
Because WhatsApp infrastructure and unofficial integrations can experience interruptions, the system prioritizes:
• transparency,
• graceful recovery,
• fault isolation,
• and user trust.
The platform assumes temporary connectivity failures may occur and is engineered to degrade gracefully rather than fail silently.
Coverage State Tracking
Each linked WhatsApp group maintains an internal coverage state.
Coverage States
StateMeaningACTIVERealtime monitoring functioning normallyDEGRADEDSession instability or delayed synchronization detectedPAUSEDBot removed, disconnected, or unable to receive messagesRECOVERINGBot rejoining and restoring synchronization state 
Bot Removal Detection
The WhatsApp connector listens for participant removal events using the underlying WhatsApp event stream.
If the listener account is:
• removed,
• disconnected,
• invalidated,
• or banned,
the system automatically:
• marks coverage as paused,
• records the outage timestamp,
• suspends realtime ingestion,
• notifies affected users.
Coverage Gap Transparency
Knowtis explicitly informs users whenever monitoring coverage is incomplete.
Example:
“Coverage paused June 1–3. Some academic updates may be missing during this period.”
This prevents:
• silent data gaps,
• false confidence,
• and inaccurate academic timelines.
Coverage history is visible within the dashboard activity timeline.
Recovery & Rejoin Logic
When a listener rejoins a group:
• the system restores the last processed checkpoint,
• resumes monitoring from the latest valid message,
• avoids replaying stale historical messages,
• and prevents duplicate reminders or false notifications.
Connector Abstraction Layer
The WhatsApp integration layer is abstracted from the core application infrastructure.
Purpose:
• isolate protocol instability,
• support future connector replacements,
• prevent ingestion failures from crashing the platform.
Example architecture:
Core Application ↓ WhatsApp Gateway Interface ↓ Baileys Adapter
This allows future migration to:
• alternative WhatsApp libraries,
• official APIs (if available),
• or custom connector services.
Graceful Degradation
If WhatsApp connectivity is temporarily unstable:
• the dashboard remains operational,
• reminders continue functioning,
• previously extracted academic events remain accessible,
• OCR and calendar features remain available.
Only realtime ingestion is paused.
Users are notified through calm system banners rather than disruptive error states.
Health Monitoring & Reliability Metrics
Knowtis maintains internal monitoring for:
• active listener sessions,
• reconnect frequency,
• join failures,
• synchronization latency,
• event ingestion delays,
• and queue health.
Critical failures trigger internal admin alerts.
Redundancy Strategy (Future Expansion)
Future infrastructure may include:
• multiple listener accounts,
• distributed ingestion workers,
• group sharding,
• isolated session pools.
Purpose:
• reduce cascading failures,
• minimize account bans,
• improve scalability,
• and increase uptime reliability.
Manual Recovery Tools
If coverage gaps occur, students may:
• manually paste missed announcements,
• upload screenshots for OCR extraction,
• or manually create academic reminders.
This ensures Knowtis remains useful even during temporary synchronization outages.
Reliability Principle
Knowtis prioritizes:
• transparency over hidden failures,
• graceful degradation over crashes,
• and trust over artificial perfection.

9.1 Rate Limiting, Abuse Prevention & Tier Enforcement
Design Philosophy
Knowtis implements intelligent rate limiting and workload controls to:
• prevent abuse,
• protect WhatsApp listener accounts,
• maintain platform stability,
• and preserve fair resource allocation across free and premium users.
Rate limiting prioritizes graceful slowdowns over hard platform failures.
Core Protection Areas
Protected Systems
• WhatsApp group joining
• OCR extraction requests
• AI query requests
• notification bursts
• authentication endpoints
• calendar synchronization
• dashboard API usage
WhatsApp Join Protection
To reduce account bans and rate limiting:
• group joins are staggered,
• randomized delays are applied,
• queue concurrency is controlled,
• join retries use exponential backoff.
Join Queue Limits
Free Tier
• Max 2 linked WhatsApp groups
• Limited concurrent onboarding priority
Premium Tier
• Unlimited linked groups
• Priority queue placement
OCR Rate Limits
OCR extraction is resource-intensive and therefore rate-limited.
Free Tier
• Limited OCR extractions per hour
• Standard processing priority
Premium Tier
• Higher OCR limits
• Faster OCR processing queue
AI Agent Usage Limits
Free Tier
Access limited to:
• predefined “Catch me up” chips,
• basic academic summaries,
• fixed query templates.
Premium Tier
Access to:
• conversational academic querying,
• semantic search,
• contextual follow-up questions,
• advanced reminder intelligence.
Notification Delivery Limits
Free Tier
• Twice-daily Night Brief summaries
• Batched notification delivery
Premium Tier
• Instant direct alerts
• Realtime event notifications
• Urgent academic interruption alerts
Dashboard Cascade Limits
Free Tier
• Top 3 closest academic events displayed
• Basic sticky note interaction
Premium Tier
• Top 5 cascading sticky notes
• Interactive source references
• Expanded event metadata
• Advanced prioritization
API Protection
All public endpoints include:
• request throttling,
• IP-based abuse detection,
• token validation,
• burst protection,
• queue overflow safeguards.
Graceful Rate Limiting
Instead of abrupt failures, users receive:
• cooldown notices,
• retry timers,
• queue status feedback,
• and soft usage warnings.
Example:
“OCR processing is temporarily busy. Please retry in 2 minutes.”
Future Expansion
Potential future controls:
• anomaly detection,
• AI abuse scoring,
• adaptive workload balancing,
• dynamic queue prioritization.

6.11 Mobile Homescreen Widgets ("Cascade Widgets")
Overview
Knowtis provides native mobile homescreen widgets that mirror the platform’s signature Sticky Note Cascade interface directly on the user’s device.
The widget system is designed to:
• surface academic urgency instantly,
• reduce the need to open the app repeatedly,
• reinforce deadlines passively throughout the day,
• and integrate Knowtis into the student’s daily workflow.
The widgets function as lightweight realtime extensions of the dashboard experience.
Design Philosophy
The widget experience prioritizes:
• glanceable information,
• calm visual hierarchy,
• low cognitive load,
• and fluid interaction.
Rather than displaying dense information, the widgets emphasize:
• the next important academic action,
• urgency visibility,
• and quick contextual awareness.
Cascade Widget Behavior
Widgets visually replicate the Sticky Note Cascade system used inside the Knowtis dashboard.
Features include:
• stacked cascading cards,
• soft layered shadows,
• pastel urgency colors,
• rounded floating sticky notes,
• smooth swipe transitions,
• animated depth effects.
Swipe & Fade Interaction
Users can swipe through sticky-note cards directly from the homescreen widget.
During interaction:
• active cards move forward,
• previous cards softly fade,
• background cards shift upward in the cascade,
• and depth transitions maintain the layered visual stack.
The interaction is designed to feel:
• lightweight,
• tactile,
• and fluid without overwhelming the user.
Widget Types
Single Focus Widget
Displays:
• the most urgent academic event,
• countdown timer,
• course code,
• event time,
• urgency color.
Best for:
• minimal setups,
• lockscreen placement,
• small widget sizes.
Cascade Stack Widget
Displays:
• top upcoming academic events,
• stacked sticky-note previews,
• swipeable reminder cards,
• realtime urgency updates.
This is the primary flagship widget experience.
Daily Brief Widget
Displays:
• upcoming deadlines,
• class schedule changes,
• exam reminders,
• and summary statistics for the day.
Example:
• “2 deadlines today”
• “1 class moved”
• “Next event: ELE 310 Quiz • 10:00 AM”
Widget Synchronization
Widgets synchronize with:
• dashboard events,
• Night Brief summaries,
• realtime notifications,
• reminder updates,
• and OCR-generated academic schedules.
Only lightweight event metadata is cached locally for fast rendering.
Platform Support
Android
Implementation via:
• Jetpack Glance,
• Android App Widgets API.
iOS
Implementation via:
• WidgetKit,
• SwiftUI-based widget rendering.
Widget Refresh Strategy
Widgets update intelligently using:
• push-triggered refreshes,
• lightweight polling,
• and cached event snapshots.
The refresh system is optimized to:
• preserve battery life,
• reduce unnecessary network requests,
• and maintain smooth homescreen performance.
Widget Personalization
Users may customize:
• widget size,
• visible event categories,
• reminder density,
• color intensity,
• and preferred urgency filters.
Premium Widget Features
Premium users receive:
• expanded cascade depth,
• interactive source links,
• richer event metadata,
• advanced reminder grouping,
• and realtime urgent-event updates.
Accessibility & UX Standards
Widgets are designed for:
• high readability,
• low visual fatigue,
• dark mode compatibility,
• smooth motion transitions,
• and touch-friendly interaction zones.
Typography and spacing prioritize quick readability under short attention windows.
Design Identity
The Cascade Widgets are intended to become a core part of the Knowtis product identity.
The homescreen itself becomes:
• an ambient academic command center,
• continuously surfacing relevant academic priorities without intrusive interaction.
This reinforces:
• organization,
• clarity,
• and calm academic awareness throughout the student’s day.

6.12 Academic Event Taxonomy & Priority Classification
Overview
Knowtis classifies academic information into structured priority categories rather than treating all detected updates equally.
This prevents:
• low-priority informational notices from competing with urgent deadlines,
• notification overload,
• and cognitive clutter inside the dashboard experience.
The system prioritizes actionable academic responsibilities over passive informational content.
Core Classification Philosophy
Not all academic updates carry the same urgency or importance.
Example:
High-priority:
• “Assignment due tomorrow by 1:30 PM”
Lower-priority:
• “NGO offering free vaccinations tomorrow”
Both may be relevant to students, but they require different:
• urgency handling,
• dashboard placement,
• notification behavior,
• and reminder intensity.
Primary Event Categories
DEADLINE
Represents academic items requiring direct student action or submission.
Examples:
• assignments,
• quizzes,
• exams,
• registrations,
• project submissions,
• fee deadlines.
EVENT
Represents scheduled academic or campus-related activities.
Examples:
• seminars,
• workshops,
• NGO programs,
• guest lectures,
• departmental meetings,
• orientation events.
ALERT
Represents urgent timeline disruptions or immediate academic changes.
Examples:
• class cancellations,
• venue changes,
• lecturer delays,
• timetable modifications,
• emergency announcements.
INFO
Represents informational or low-urgency notices.
Examples:
• scholarship notices,
• internship opportunities,
• student announcements,
• awareness campaigns,
• club notices.
Priority Hierarchy
The system prioritizes categories in the following order:
• ALERT
• DEADLINE
• EVENT
• INFO
This priority order affects:
• dashboard positioning,
• sticky-note visibility,
• widget rendering,
• notification timing,
• and Night Brief summaries.
Dashboard Separation
The dashboard visually separates:
Academic Deadlines
High-priority actionable items displayed using the Sticky Note Cascade interface.
Events & Notices
Displayed in a lighter informational feed with reduced urgency styling.
Informational Updates
Collapsed or deprioritized unless manually expanded by the user.
Notification Logic
DEADLINE Notifications
• aggressive reminder scheduling,
• countdown visibility,
• optional instant alerts,
• recurring reminder support.
ALERT Notifications
• immediate delivery,
• highest notification priority,
• realtime push support.
EVENT Notifications
• summarized in Night Briefs,
• optional reminder opt-in,
• lower interruption priority.
INFO Notifications
• bundled into digest summaries,
• low interruption behavior,
• optionally hidden by user preference.
Sticky Note Behavior
Only high-priority items appear in the primary Sticky Note Cascade.
Default cascade behavior prioritizes:
• deadlines,
• urgent alerts,
• imminent academic actions.
Informational notices are intentionally excluded from the main cascade unless pinned by the user.
Widget Prioritization
Homescreen widgets prioritize:
• ALERTS
• DEADLINES
• Upcoming EVENTS
INFO-level content is generally excluded from compact widget views to maintain clarity.
AI Classification Pipeline
The AI pipeline assigns:
• semantic category,
• urgency score,
• confidence score,
• actionability score.
These values influence:
• reminder generation,
• event ranking,
• feed placement,
• and notification escalation.
User Personalization (Future Expansion)
Future personalization options may allow students to:
• mute specific categories,
• prioritize departmental events,
• suppress informational notices,
• or customize urgency behavior.
Design Philosophy
Knowtis prioritizes:
• actionable clarity,
• low cognitive load,
• and intelligent urgency management.
The goal is not to show every academic message, but to surface what genuinely matters most to the student at the right time.

9.2 In-App Subscription Architecture (Google Play First)
Overview
The initial mobile deployment will target Android via the Google Play Store.
To ensure secure transaction processing and a frictionless future expansion
to the iOS App Store, the system utilizes RevenueCat as a subscription
management wrapper. This abstracts Google Play Billing complexity and
standardizes cross-platform receipt validation.
Payment & Validation Flow
• The mobile client fetches available Premium plans dynamically via the
RevenueCat SDK.
• User initiates an upgrade, triggering the native Google Play billing
bottom sheet.
• Upon successful payment, Google Play issues a cryptographic purchase
token to the device.
• The RevenueCat SDK automatically captures and forwards this token to
RevenueCat servers.
• RevenueCat performs server-to-server validation with Google to verify
the transaction's authenticity.
Backend Synchronization (FastAPI)
• The FastAPI backend relies on secure webhooks from RevenueCat (e.g.,
INITIAL_PURCHASE, RENEWAL, EXPIRATION).
• Webhook payloads trigger immediate updates to the user's is_premium
status within the PostgreSQL database.
• Core application features (e.g., AI Agent conversational mode, limits
on linked groups, and OCR extraction ceilings) enforce access control
by referencing this local database state.
• Storing the entitlement state locally ensures the app degrades
gracefully and maintains functionality even during temporary external
billing outages.
Analytics & Monitoring
• Subscription analytics, active user states, MRR, and churn metrics are
monitored directly through the native RevenueCat Overview Dashboard.
• This eliminates the engineering overhead of building and maintaining a
custom API-driven internal financial dashboard while providing
realtime visibility into product performance.
Infrastructure Prerequisites
• Active Google Play Console Developer account.
• Linked Google Payments Merchant profile configured for regional
payouts.
• Defined Subscription Tiers and Base Plans within the Play Console that
mirror the Knowtis Free/Premium monetization matrix.
