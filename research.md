
A Feasibility Study and Architectural Blueprint for Integrating EPA CompTox Models with the Model Context Protocol


Executive Summary

This report presents a comprehensive feasibility analysis and architectural blueprint for developing a Model Context Protocol (MCP) interface for the diverse suite of computational models associated with the U.S. Environmental Protection Agency's (EPA) CompTox Chemicals Dashboard. The central finding is that creating such an interface is technically possible but represents a significant and architecturally complex undertaking. The project's scope extends beyond simple technical integration; it offers a transformative opportunity to establish a next-generation platform for computational toxicology, enabling automated, AI-driven chemical risk assessment, data gap filling, and advanced research workflows.
The CompTox ecosystem is characterized by a high degree of heterogeneity, comprising standalone desktop applications, modern web services, command-line tools, and vast data pipelines. This diversity reflects the historical evolution of the field and necessitates a sophisticated, multi-faceted integration strategy rather than a monolithic solution. The Model Context Protocol, an emerging open standard for connecting AI systems to external tools and data, provides the ideal framework for this task due to its architectural flexibility, robust open-source ecosystem, and support for both local and remote resources.
The proposed architecture is a distributed system of specialized MCP "micro-servers," each responsible for exposing a specific model or data source. This modular design promotes scalability, fault isolation, and independent development. The blueprint outlines a phased implementation, beginning with foundational data servers, progressing to the encapsulation of predictive models, and culminating in the development of a high-level "Orchestrator" server capable of executing complex, multi-step scientific workflows.
Crucially, this report argues that the project's ultimate feasibility and scientific integrity are contingent upon a meticulously planned implementation that treats model metadata, validation principles, and applicability domains as first-class, machine-readable citizens within the protocol. A core recommendation is the development of a standardized, computable "CompTox Model Card" schema, based on established frameworks like the OECD principles for QSAR validation. This would be coupled with mandatory, programmatic "applicability domain" checks that function as automated safety guardrails, preventing the misuse of models outside their validated chemical space.
Success in this endeavor is not merely about connecting models to an AI; it is about connecting them responsibly. By embedding principles of scientific rigor, transparency, and caution directly into the protocol's fabric, this initiative can establish a new gold standard for the responsible application of artificial intelligence in a regulatory science context, dramatically accelerating the pace of chemical safety evaluation while enhancing its reproducibility and reliability.

Section 1: The CompTox Computational Ecosystem: A Landscape of Heterogeneity

A successful integration strategy must begin with a deep and nuanced understanding of the target environment. The EPA's CompTox Chemicals Dashboard and its associated computational tools do not form a homogenous system but rather a complex, evolving ecosystem of data, software, and predictive models. This heterogeneity presents the primary architectural challenge and dictates the design of any unifying protocol.

1.1 The CompTox Chemicals Dashboard as a Data Aggregation Hub

The CompTox Chemicals Dashboard serves as the public-facing hub for the EPA's computational toxicology research, providing a "first-stop-shop" for chemistry, toxicity, and exposure information for over one million chemical substances.1 Its fundamental role is that of a data aggregator, integrating a vast array of information from disparate sources into a single, searchable interface. These sources include the EPA's own large-scale research programs and databases, such as the Toxicity Forecaster (ToxCast) and the Toxicity Reference Database (ToxRefDB), as well as numerous public domain resources, including the National Center for Biotechnology Information's PubChem database.1
The Dashboard provides access to chemical structures, experimental and predicted physicochemical properties, environmental fate and transport data, hazard assessments, and bioactivity data from high-throughput screening.5 This aggregation provides immense value to researchers and regulators by saving significant time and effort in data collection. However, it also introduces a critical governance constraint that must be respected by any automated system built upon it. The EPA provides an explicit disclaimer stating that the Dashboard is a compilation of information from many sources and that "The data are not reviewed by USEPA - the user must apply judgment in use of the information".4 This places the onus of critical evaluation and scientific judgment squarely on the user. For an automated AI agent, this is a profound challenge. An AI cannot be permitted to naively consume and act upon this data without a programmatic awareness of its unreviewed status and provenance. This elevates the integration project from a simple technical task to one that must codify and enforce principles of scientific caution.

1.2 Inventory and Architectural Categorization of Computational Models

The computational "models" available through the CompTox Dashboard are not a uniform set of APIs. They represent a collection of tools and systems developed over many years, each with its own distinct architectural pattern. This diversity is not a flaw but rather an archaeological record of the evolution of computational toxicology, reflecting a broader shift in scientific computing from standalone, desktop-based tools to integrated, web-native platforms. A one-size-fits-all integration strategy is therefore destined to fail. The approach must be a "brownfield" integration, adept at encapsulating and modernizing legacy systems, rather than a "greenfield" project that assumes modern, homogenous interfaces.
The models can be systematically classified into several architectural categories:
Category 1: Standalone, Downloadable Software: These are typically older, self-contained applications designed to be run on a user's local machine.
Example: TEST (Toxicity Estimation Software Tool). TEST is a prime example of this category. It is a Java-based desktop application that allows users to estimate toxicity and physicochemical properties using various Quantitative Structure-Activity Relationship (QSAR) methodologies.7 The user inputs a chemical structure, and the software performs calculations locally to produce an estimate.7 Its primary mode of interaction is through a graphical user interface or command-line execution, posing a significant challenge for integration with a web-based protocol like MCP.
Category 2: Integrated Web Applications & Services: These represent a more modern approach, offering functionality through a web browser and, in some cases, underlying web services.
Example: GenRA (Generalized Read-Across). GenRA is a web application, tightly integrated with and accessible directly from the Dashboard, designed to automate the process of read-across for data gap filling.1 It has a defined, multi-step workflow for analogue identification, evaluation, and prediction.11 Its nature as a modern web application suggests the likely presence of internal APIs, making it a more straightforward candidate for MCP integration.
Example: WebTEST. The existence of a "Web-services Toxicity Estimation Software Tool" (WebTEST) indicates the EPA's recognition of the need for service-oriented architecture.13 While documentation points to an older version, it establishes a precedent for exposing TEST's functionality via a web API.14
Category 3: Model Suites and Data Pipelines: These are not single, executable models but rather collections of models or large-scale data processing systems whose outputs are consumed within the Dashboard.
Example: OPERA (Open Structure-activity/property Relationship App). OPERA is a comprehensive suite of curated, validated QSAR models developed in collaboration between the National Toxicology Program's Interagency Center for the Evaluation of Alternative Toxicological Methods (NICEATM) and the EPA.15 While OPERA is available as a standalone command-line application, its predictions for over 750,000 chemicals are also pre-computed and integrated directly into the Dashboard's data tabs.16 This dual nature—an executable tool versus a source of static, predicted data—is a key architectural consideration for an MCP implementation.
Example: ToxCast/invitroDB. ToxCast is less a single model and more a massive data generation and processing pipeline. It utilizes high-throughput screening to generate bioactivity data on thousands of chemicals across hundreds of assays.1 This data is stored in invitroDB and serves as a foundational input for other models and analyses, such as GenRA.5 An MCP server for ToxCast would primarily function as a data source provider rather than a computational engine.
Category 4: Exposure and Toxicokinetic Modeling Frameworks: These are complex, multi-component systems that model intricate biological and environmental processes.
Examples: SEEM (Systematic Empirical Evaluation of Models) and HTTK (High-throughput Toxicokinetics). These frameworks are used to predict chemical exposure and Absorption, Distribution, Metabolism, and Excretion (ADME), respectively.1 SEEM uses a combination of models to predict exposure from industrial releases and consumer products, while HTTK models use in vitro data to predict in vivo toxicokinetics.19 They represent sophisticated scientific workflows that require multiple inputs and produce complex outputs, demanding a more nuanced MCP interface than a simple predictive function.
To effectively scope the integration effort, these assets are summarized in the following table.

Model/Tool Name
Model Type
Primary Function
Architectural Pattern
TEST (Toxicity Estimation Software Tool)
QSAR
Predicts acute toxicity (e.g., ) and physicochemical properties for organic chemicals using multiple methodologies.7
Standalone Executable (Java Application)
OPERA (Open... Relationship App)
QSAR Suite
Predicts a wide range of physicochemical, environmental fate, ADME, and toxicity endpoints with OECD-compliant models.15
Command-Line Tool & Pre-computed Data Source
GenRA (Generalized Read-Across)
Read-Across
Fills data gaps for a target chemical by making predictions based on structurally and/or biologically similar source analogues.9
Integrated Web Application
ToxCast / invitroDB
High-Throughput Screening Data Pipeline
Generates and provides access to bioactivity data from thousands of chemicals tested in hundreds of in vitro assays.1
Data Source / Pipeline
SEEM (Systematic Empirical Eval. of Models)
Exposure Modeling Framework
Predicts human exposure to chemicals from far-field (industrial) and near-field (consumer product) sources.1
Modeling Framework / Data Source
HTTK (High-throughput Toxicokinetics)
IVIVE / PBPK
Predicts chemical ADME properties, enabling in vitro to in vivo extrapolation (IVIVE) of bioactivity data.4
Modeling Framework / Data Source

Table 1: Inventory of Key CompTox Computational Models and Tools

Section 2: The Model Context Protocol as a Unifying Scientific Gateway

To bridge the heterogeneous landscape of the CompTox ecosystem, a flexible, powerful, and standardized communication layer is required. The Model Context Protocol (MCP) is an open standard, introduced by Anthropic in late 2024, designed specifically for this purpose: to standardize how AI systems, such as large language models (LLMs), integrate and interact with external tools, data sources, and systems.20 MCP is not merely another API specification; it is a framework designed to enable complex, multi-step, and autonomous workflows, making it uniquely suited for the challenges of scientific discovery.

2.1 Deconstructing the MCP Architecture

MCP is built on a client-server architecture that provides a standardized, two-way connection for AI applications.21 This architecture consists of three primary components:
MCP Host: This is the AI application or environment where the LLM resides, such as a conversational AI chat interface or an AI-powered integrated development environment (IDE). It is the user's primary point of interaction.21
MCP Client: Located within the host, the client acts as a translator. It takes the LLM's intent to use a tool, formats it into a standardized MCP request, and sends it to the appropriate server. It also receives the server's response and formats it for the LLM.21
MCP Server: This is the external service that provides the data or computational capability. An MCP server exposes a set of "tools" (functions) that the LLM can invoke. For the CompTox project, each computational model or data source would be wrapped in its own MCP server.21
Communication between the client and server is handled by a well-defined transport layer using JSON-RPC 2.0 messages.21 This layer is critically important for the CompTox use case because it supports multiple transport methods. For local, standalone applications like TEST, the stdio (standard input/output) method can be used for fast, synchronous communication. For remote web services like GenRA, the Server-Sent Events (SSE) method is preferred for efficient, real-time data streaming.21 This inherent flexibility directly addresses the architectural heterogeneity identified in Section 1.
Furthermore, MCP is an open standard with a rapidly growing ecosystem, including official Software Development Kits (SDKs) in numerous programming languages such as Python, TypeScript, Java, and C#.20 This robust support significantly lowers the development barrier for creating both MCP clients and servers, accelerating the implementation process.

2.2 MCP as an Enabler of Agentic AI for Scientific Discovery

The true power of MCP lies in its ability to move beyond simple, one-shot interactions like basic function calling or Retrieval-Augmented Generation (RAG). While RAG allows an LLM to retrieve information to answer a question, MCP enables an AI to become an agent—an active participant in a complex, multi-step workflow. It can request data from one source, use that data to invoke a computational model on another server, analyze the result, and then decide on the next action in a logical sequence.21 This capability unlocks several key benefits in a scientific context:
Reduced Hallucinations: LLMs can sometimes generate plausible but incorrect information ("hallucinate") because their knowledge is based on static training data.21 By grounding the LLM in real-time computations from validated scientific models and direct queries to authoritative databases, MCP ensures that responses are based on verifiable data, dramatically increasing their reliability.
Increased Utility and Automation: MCP transforms an LLM from a passive information source into an active research assistant. A scientist is no longer required to manually operate each tool in sequence. Instead, they can issue a high-level, natural language command like: "For the chemical with CASRN 50-78-2, predict its physicochemical properties using OPERA, estimate its oral rat  using the TEST consensus method, find three structural analogues using GenRA with Morgan fingerprints, and summarize the potential hazards in a brief report." An MCP-enabled AI agent could parse this request and autonomously execute the entire workflow.
Standardization and Interoperability: MCP acts as a universal adapter, akin to a "USB-C for scientific models".23 It provides a uniform method for an AI to interact with a diverse set of tools developed by different teams, at different times, using different technologies. This creates a cohesive and interoperable ecosystem where new models can be "plugged in" with minimal integration overhead.
This functionality represents a paradigm shift in how scientists interact with computational tools. The current model requires the scientist to be a "tool operator," manually moving data between different interfaces and software. The MCP-enabled model elevates the scientist to a "workflow director," who specifies the high-level scientific objective and delegates the low-level, mechanistic execution to an AI agent. This abstraction promises to dramatically increase the efficiency and throughput of computational research, potentially enabling the discovery of novel connections as the AI can execute and synthesize results from disparate models at a scale and speed unattainable by a human.
The decision to adopt MCP is further de-risked by its rapid, industry-wide adoption. Following its open-sourcing, the protocol has been embraced by major AI providers, including OpenAI and Google DeepMind, and integrated into key development tools.20 This strong industry consensus indicates that MCP is not a niche or experimental technology but is quickly becoming the de facto standard for AI tool integration. Building on this standard ensures future compatibility, access to a large and growing talent pool, and the ability to leverage a rich ecosystem of supporting tools and infrastructure.

Section 3: An Architectural Blueprint for an MCP-Enabled CompTox Framework

Translating the strategic vision into a tangible technical solution requires a concrete architectural blueprint. This section proposes a pragmatic, phased implementation plan designed to manage complexity, deliver incremental value, and ensure the resulting system is robust, scalable, and scientifically sound. The proposed architecture is not a single, monolithic application but a distributed system of specialized, interoperable MCP micro-servers.

3.1 A Phased Integration Strategy

A "big bang" approach to integrating the entire CompTox model suite would be fraught with risk. A phased strategy is essential to manage technical complexity, demonstrate value early, and allow for iterative refinement based on user feedback and evolving requirements.
Phase I: Foundational Data & Metadata Servers
The initial phase focuses on exposing the core, foundational datasets of the CompTox Dashboard as read-only MCP servers. This is the lowest-risk, highest-value starting point, as it provides immediate utility by allowing AI agents to query essential chemical information without involving complex computational models. This phase would also include the development of a critical ModelMetadataServer.
Example Server: DSSToxServer. Exposes tools for retrieving chemical identity and structure information from the Distributed Structure-Searchable Toxicity (DSSTox) database. A key tool would be dsstox.get_chemical_by_id(id: str), which returns canonical information like structure, CASRN, and synonyms.
Example Server: ToxCastServer. Provides programmatic access to the vast in vitro bioactivity data from the ToxCast program. A tool like toxcast.get_bioactivity_by_chemical(dtxsid: str) would return a structured summary of assay results for a given chemical.
Example Server: ModelMetadataServer. This is a cornerstone of the entire architecture. It will not serve chemical data but rather metadata about the models themselves. Its primary tool, metadata.get_model_card(model_name: str), will return a standardized, machine-readable document detailing a model's capabilities, limitations, and validation status, as will be detailed in Section 4.
Phase II: Encapsulation of Predictive Models as MCP Servers
This phase addresses the core challenge of making the predictive models accessible via MCP. The strategy will vary based on the architectural pattern of each model.
Strategy for Standalone Tools (e.g., TEST): An MCP server will be designed to act as a "harness" or "wrapper" around the standalone executable. When the server receives an MCP request, its logic will:
Receive the input chemical structure (e.g., as a SMILES string).
Write the structure to a temporary input file in a format the tool understands.
Execute the TEST command-line process, using the MCP stdio transport for communication.7
Monitor the process for completion and capture the generated output files.
Parse the output files (e.g., text reports or structured data) and format the results into a standardized JSON response.
Return the JSON response to the MCP client.
Strategy for Command-Line Tools (e.g., OPERA): The approach is similar to that for standalone tools. A wrapper server will invoke the OPERA command-line interface, pass the necessary arguments, and parse the standard output to construct a structured JSON response.15
Strategy for Web Applications (e.g., GenRA): This represents the most straightforward integration path. A dedicated MCP server will be developed to act as an API client to the GenRA web application. It will translate MCP requests into the appropriate HTTP requests for the GenRA backend and format the JSON response back into the MCP standard. This assumes a stable, documented, or reverse-engineerable API for GenRA exists.9
Phase III: The Orchestrator Meta-Server
With the foundational data and model servers in place, the final phase involves developing a higher-level MCP server that embodies complex, multi-step scientific workflows. This "Orchestrator" would not perform computations itself but would instead orchestrate calls to the other, more primitive servers.
Function: This server would understand and execute complex queries that require a sequence of operations. For instance, a request to orchestrator.run_preliminary_risk_assessment(smiles: str) would trigger an internal logic sequence:
Call dsstox.get_chemical_by_id to validate the structure and get identifiers.
Concurrently call opera.predict_property for multiple endpoints (e.g., logP, water solubility).
Call test.predict_toxicity for acute toxicity.
Call genra.find_analogues to identify similar chemicals.
Synthesize the results from all preceding calls into a coherent, summary response for the LLM.
This Orchestrator server effectively codifies the expert knowledge of a toxicologist, transforming a collection of disparate tools into an intelligent, automated assessment workflow. The logic contained within this server becomes a new and valuable form of institutional intellectual property.

3.2 Proposed MCP Tool Definitions

To make this architectural blueprint concrete and actionable, the following table provides preliminary definitions for the MCP tools that would be exposed by the various servers. These definitions serve as a starting point for development, clarifying the scope, inputs, and outputs for each function an AI agent could call.
MCP Tool Name
Description
Input Parameters (JSON Schema)
Output Schema (JSON Schema)
Target CompTox Model/Data
metadata.get_model_card
Retrieves the machine-readable Model Card for a specified computational model.
{"model_name": {"type": "string", "enum":}}
{"model_card": {"type": "object", "$ref": "#/definitions/CompToxModelCard"}}
CompTox Model Card Schema
test.predict_consensus_toxicity
Predicts a specified toxicity endpoint using the TEST consensus method.
{"chemical_identifier": {"type": "string", "description": "SMILES string"}, "endpoint": {"type": "string", "enum": ["oral_rat_ld50", "fathead_minnow_lc50"]}}
{"prediction_value": "float", "units": "string", "ad_status": "string", "ad_confidence": "float"}
TEST v5.1.2
test.check_applicability_domain
Checks if a chemical is within the applicability domain (AD) of the specified TEST model.
{"chemical_identifier": {"type": "string"}, "endpoint": {"type": "string"}}
{"in_domain": "boolean", "confidence_score": "float", "neighbors": ["string"]}
TEST v5.1.2
opera.predict_property
Predicts a specified physicochemical or environmental fate property using the OPERA model suite.
{"chemical_identifier": {"type": "string"}, "property": {"type": "string", "enum": ["logp", "water_solubility", "boiling_point"]}}
{"prediction_value": "float", "units": "string", "ad_status": "string", "ad_confidence": "float"}
OPERA v2.6+
genra.find_analogues
Finds the top K nearest neighbor analogues for a target chemical based on a specified fingerprint.
{"chemical_identifier": {"type": "string"}, "fingerprint_type": {"type": "string", "enum": ["morgan", "maccs", "toxcast"]}, "k": {"type": "integer", "default": 10}}
{"analogues": [{"dtxsid": "string", "name": "string", "similarity_score": "float"}]}
GenRA Web Application
genra.predict_from_analogues
Performs a read-across prediction for a specific toxicity effect based on identified analogues.
{"chemical_identifier": {"type": "string"}, "toxicity_effect": {"type": "string"}, "fingerprint_type": {"type": "string"}}
{"prediction": "string", "confidence_score": "float", "supporting_analogues": "integer"}
GenRA Web Application

Table 2: Proposed MCP Tool Definitions for CompTox Models

Section 4: Mandating Scientific Rigor: Model Cards and Applicability Domains as First-Class Citizens

The technical integration of the CompTox models via MCP is only half the challenge. For the resulting system to be scientifically valid, trustworthy, and responsible—especially within a regulatory context—it is imperative that principles of transparency and scientific rigor are not treated as an afterthought but are embedded into the very fabric of the protocol. Exposing a predictive model as an opaque "black box" API is scientifically and ethically untenable. An AI agent, or a human user, could easily generate a prediction for a chemical for which the model is not suited, leading to a dangerously incorrect conclusion with potential public health consequences.
This section proposes a framework for operationalizing responsible AI by making model documentation and constraints core, machine-readable components of the MCP interface. This transforms documentation from a static, human-readable artifact into a dynamic, computable element of the AI workflow, creating a system of programmatic guardrails.

4.1 The Ethical Imperative for Transparency and Model Cards

The concept of "Model Cards," first proposed by researchers in 2018, provides a standardized framework for documenting a machine learning model's performance, limitations, ethical considerations, and intended use.26 A model card serves as a "nutrition label" for an AI model, providing key information in a clear, digestible format to help developers and users make informed decisions.28 For the CompTox MCP project, the adoption of a rigorous, standardized model card for every exposed computational model is a non-negotiable requirement.

4.2 A Standardized "CompTox Model Card" Schema

To be useful to an AI agent, the model card cannot be a mere PDF document. It must be a structured, machine-readable JSON object, retrievable via the ModelMetadataServer proposed in Section 3. This report proposes the creation of a "CompTox Model Card" schema specifically tailored to the needs of computational toxicology, integrating general best practices with domain-specific regulatory requirements. This schema would be built upon the five principles for QSAR model validation established by the Organisation for Economic Co-operation and Development (OECD), which are crucial for regulatory acceptance.30
The key fields of the proposed JSON schema would include:
modelDetails: Basic information such as the model's name, version, developers, and a brief overview of its function.28
intendedUse: A clear description of the model's purpose, including the specific use cases that are in and out of scope (e.g., "predicts acute aquatic toxicity for non-ionic organic chemicals").28
oecdValidationPrinciples: A structured object detailing the model's compliance with the five OECD principles 31:
definedEndpoint: A precise, unambiguous definition of the biological or physicochemical endpoint the model predicts (e.g., "96-hour fathead minnow 50 percent lethal concentration ()").31
unambiguousAlgorithm: A description of the mathematical model and a link to the primary publication or technical documentation detailing the algorithm (e.g., for OPERA, a citation to Mansouri et al., 2018 16).
definedApplicabilityDomain: A machine-readable definition of the model's applicability domain (AD), as detailed in the next section.
goodnessOfFitMetrics: A collection of quantitative performance metrics from both internal and external validation procedures, such as the coefficient of determination for the training set (), the leave-one-out cross-validation coefficient of determination (), and the root mean square error (RMSE) for the external test set.7
mechanisticInterpretation: A scientific explanation, where possible, of how the model's descriptors relate to the biological mechanism underlying the predicted endpoint.31
trainingData: A description of the dataset used to train the model, including its source, size, and any curation procedures applied.28
evaluationData: A description of the external test set used for validation and the specific validation methodology employed (e.g., k-fold cross-validation, train-test split ratios).28
ethicalConsiderations: Disclosure of any potential biases or limitations that could have ethical implications.28

4.3 The Applicability Domain (AD) as a Programmatic Guardrail

The single most important component of a model card for preventing misuse is the Applicability Domain (AD). The AD defines the boundaries of the chemical and/or response space for which a QSAR model has been developed and validated, and for which it is expected to provide reliable predictions.17 A prediction for a chemical that falls outside the AD is an extrapolation and is considered unreliable.
To operationalize this principle, the MCP architecture must enforce a mandatory "safety check" workflow. Every predictive MCP server (e.g., TESTServer, OPERAServer) must not only expose a tool for making predictions but also a companion tool for checking the AD.
The proposed mandatory workflow for an AI agent would be:
The AI agent forms an intent to call a predictive tool, for example, opera.predict_property(chemical, 'logp').
Before executing the prediction, the agent's underlying logic must first call the corresponding AD check tool: opera.check_applicability_domain(chemical, 'logp').
This AD tool will execute a defined algorithm (e.g., based on structural similarity to the training set, leverage statistics, etc.) and return a structured response, such as {"in_domain": true, "confidence_score": 0.95, "nearest_neighbors":}.
The agent's logic will only proceed with the predict_property call if the in_domain status is true.
Furthermore, the final prediction result returned by predict_property must itself include the AD status and confidence score, creating a clear, auditable trail of this safety check.
This workflow transforms the AD from a passive concept in a document into an active, programmatic guardrail. It is the architectural equivalent of moving from a warning label on a piece of machinery to an automated safety shutoff that prevents operation in an unsafe condition. This system creates a powerful incentive for model developers: to have a model included and used within the CompTox MCP ecosystem, they must provide not only the model itself but also a complete, validated model card and a robust, computable AD algorithm. This requirement has the potential to drive higher standards of documentation, validation, and transparency throughout the entire field of computational toxicology.

Section 5: Feasibility Analysis: Opportunities, Risks, and Strategic Recommendations

Synthesizing the architectural blueprint and the principles of scientific rigor, this final section provides a balanced assessment of the project's overall feasibility. It weighs the transformative potential against the inherent risks and concludes with a set of concrete, strategic recommendations for a path forward.

5.1 Transformative Opportunities

The successful implementation of an MCP-enabled CompTox framework would unlock significant, transformative opportunities for chemical safety assessment and regulatory science:
Democratization of Access: By enabling complex queries in natural language, the system would dramatically lower the barrier to entry for using these powerful computational tools. Regulators, academic researchers, industry scientists, and even students could ask sophisticated questions without needing to be expert users of each individual piece of software.
Automation of Regulatory Workflows: Many routine tasks in chemical assessment, such as preliminary hazard identification for new chemicals, data gap analysis, and chemical categorization, could be radically accelerated. Workflows that currently take days or weeks of manual effort could potentially be completed in minutes.
Enhanced Research and Reproducibility: The framework would create a standardized platform where complex computational experiments can be defined, executed, logged, and shared in a highly reproducible manner. This would improve the transparency and reliability of computational toxicology research.
Novel Hypothesis Generation: An AI agent could be tasked with systematically screening vast virtual chemical libraries, combining outputs from exposure, hazard, and ADME models in novel ways to identify and prioritize chemicals of high concern or potential safer alternatives for further experimental investigation.

5.2 Risks and Mitigation Strategies

While the opportunities are substantial, the project is not without significant risks. A clear-eyed assessment of these risks and the formulation of proactive mitigation strategies are essential for success.
Technical Risk: Model and Architectural Heterogeneity.
Risk: The diverse nature of the CompTox models, from legacy desktop applications to modern web services, presents a major integration challenge. A single approach will not work for all components.
Mitigation: The phased, micro-server architecture outlined in Section 3 is the primary mitigation. By developing specific "wrapper" strategies for each architectural pattern (e.g., stdio harness for TEST, API client for GenRA), the complexity is broken down into manageable, independent modules.
Scientific Risk: Misuse and Misinterpretation of Model Outputs.
Risk: This is the most critical risk. An AI agent, if not properly constrained, could generate and present a model prediction that is scientifically invalid (e.g., for a chemical outside the AD), leading to flawed decision-making.
Mitigation: The framework detailed in Section 4 is the direct mitigation for this risk. The mandatory, programmatic inclusion of machine-readable Model Cards and the enforced "check AD before predict" workflow serve as non-negotiable safety guardrails. Furthermore, the AI's responses must be conditioned to always cite the model version used, its AD status, and a confidence score for any prediction it presents.
Operational Risk: Computational Cost and Long-Term Maintenance.
Risk: Running a large number of computational models on demand could incur significant computational costs. The maintenance of numerous MCP server wrappers could become a substantial burden over time.
Mitigation: The architecture should be designed for cloud-native deployment, using scalable and cost-effective solutions like serverless functions (e.g., AWS Lambda, Google Cloud Functions) to run model computations on demand. Adopting an open-source development model (see recommendations) can distribute the maintenance burden across a community of stakeholders.24 A clear governance model will be essential for managing contributions and ensuring quality.
Security Risk: Prompt Injection and Tool Misuse.
Risk: As with any system that connects LLMs to external tools, there are security vulnerabilities. Malicious actors could attempt "prompt injection" attacks to trick the AI into executing unintended actions, or they could exploit vulnerabilities in the tool wrappers themselves.20
Mitigation: A multi-layered security approach is required. This includes robust authentication and authorization on all MCP servers to control access, rigorous input sanitization to prevent injection attacks, and sandboxing the execution environments for standalone models like TEST to contain any potential exploits. Implementing rate-limiting and monitoring is also crucial to prevent denial-of-service attacks and detect anomalous behavior.

5.3 Strategic Recommendations

Based on the comprehensive analysis, the following strategic recommendations provide a clear and pragmatic path forward for realizing the vision of an MCP-enabled CompTox ecosystem:
Initiate a Pilot Project with Well-Suited Candidates: Instead of attempting a full-scale implementation, begin with a tightly scoped pilot project focused on two or three high-value models. The ideal candidates for this pilot are OPERA and GenRA. OPERA is well-documented, its models are built according to OECD principles, and it exists as a command-line tool, making it a perfect test case for the "wrapper" strategy.16 GenRA has a modern web architecture, making it a good test case for API-based integration.9 Success with these two models would validate the core architectural patterns.
Prioritize the Development of the Metadata Framework: The very first development task of the pilot project should be the creation, ratification, and implementation of the "CompTox Model Card" JSON schema and the foundational ModelMetadataServer. This act establishes the primacy of scientific rigor and transparency from the outset and sets the standard against which all subsequent model integrations will be measured.
Adopt an Open-Source Development Model: The MCP itself is an open-source project with a vibrant community.24 The CompTox MCP servers should be developed under a similar model. Hosting the code in a public repository (e.g., on GitHub) would encourage collaboration from academia, industry partners, and other international regulatory bodies. This approach would not only accelerate development but also distribute the long-term maintenance burden and foster broader adoption and trust in the platform.
Establish a Multi-Disciplinary Governance Committee: The project's success requires more than just technical expertise. A formal governance committee should be established, comprising toxicologists, cheminformaticians, data scientists, AI architects, and regulatory affairs specialists. This committee would be responsible for overseeing the project, ratifying the Model Card schema, validating the scientific integrity of each model integration, and ensuring that the system's development remains aligned with the EPA's mission and scientific principles.

Conclusion

The integration of the EPA's CompTox Chemicals Dashboard models with the Model Context Protocol is not only technically feasible but represents a strategically imperative evolution for the field of chemical risk assessment. The proposed architectural blueprint, centered on a distributed system of specialized MCP servers and a phased implementation, provides a viable path for navigating the technical complexities of the heterogeneous CompTox ecosystem. This endeavor promises to democratize access to powerful computational tools, automate and accelerate critical regulatory workflows, and unlock new avenues for scientific research by enabling AI-driven hypothesis generation at an unprecedented scale.
However, the analysis unequivocally concludes that the project's feasibility is inextricably linked to its commitment to scientific integrity. The transformative potential of this system can only be safely realized if the principles of transparency, validation, and responsible use are not merely considered but are programmatically enforced. The mandatory implementation of machine-readable Model Cards based on OECD principles and the non-negotiable use of Applicability Domains as automated guardrails are the foundational pillars upon which this entire structure must be built. The ultimate success of this endeavor will be measured not by the elegance of its code, but by the unwavering fidelity with which it embeds the principles of sound science into the very fabric of its architecture.
Works cited
CompTox Chemicals Dashboard - Environmental Protection Agency (EPA), accessed October 14, 2025, https://www.epa.gov/system/files/documents/2022-06/chemicals_dashboard_march2022.pdf
CompTox Chemicals Dashboard | US EPA, accessed October 14, 2025, https://www.epa.gov/comptox-tools/comptox-chemicals-dashboard
US EPA's First-Stop-Shop for Chemical Information: The CompTox Chemicals Dashboard, accessed October 14, 2025, https://www.naccho.org/blog/articles/us-epas-first-stop-shop-for-chemical-information-the-comptox-chemicals-dashboard
CompTox Chemicals Dashboard: About | US EPA, accessed October 14, 2025, https://www.epa.gov/comptox-tools/comptox-chemicals-dashboard-about
CompTox Chemicals Dashboard Resource Hub | US EPA, accessed October 14, 2025, https://www.epa.gov/comptox-tools/comptox-chemicals-dashboard-resource-hub
Sources CompTox Dashboard - eChemPortal, accessed October 14, 2025, https://www.echemportal.org/echemportal/content/participants/600
Toxicity Estimation Software Tool (TEST) | US EPA, accessed October 14, 2025, https://www.epa.gov/comptox-tools/toxicity-estimation-software-tool-test
T.E.S.T. (Toxicity Estimation Software Tool), accessed October 14, 2025, https://www.epa.gov/system/files/documents/2024-07/introduction-test_508.pdf
Generalized Read-Across (GenRA) | US EPA, accessed October 14, 2025, https://www.epa.gov/comptox-tools/generalized-read-across-genra
GenRA Manual: Web Application | US EPA, accessed October 14, 2025, https://www.epa.gov/comptox-tools/genra-manual-web-application
Generalised Read-Across (GenRA), accessed October 14, 2025, https://www.epa.gov/system/files/documents/2022-02/genra_help_080222.pdf
Generalized Read-Across (GenRA) Manual | US EPA, accessed October 14, 2025, https://www.epa.gov/comptox-tools/generalized-read-across-genra-manual
User's Guide for WebTEST (version 1.0) (Web-services Toxicity Estimation Software Tool), accessed October 14, 2025, https://www.epa.gov/comptox-tools/users-guide-webtest-version-10-web-services-toxicity-estimation-software-tool
User's Guide for WebTEST (version 1.0) (Web-services Toxicity Estimation Software Tool), accessed October 14, 2025, https://19january2021snapshot.epa.gov/chemical-research/users-guide-webtest-version-10-web-services-toxicity-estimation-software-tool_.html
OPERA - National Toxicology Program, accessed October 14, 2025, https://ntp.niehs.nih.gov/whatwestudy/niceatm/comptox/ct-opera/opera
OPERA models for predicting physicochemical properties and environmental fate endpoints - PMC - National Institutes of Health (NIH) |, accessed October 14, 2025, https://pmc.ncbi.nlm.nih.gov/articles/PMC5843579/
OPERA models for predicting physicochemical properties and environmental fate endpoints - Green Chemistry For Sustainability, accessed October 14, 2025, https://chemistryforsustainability.org/sites/default/files/2025-07/mansouri2018.pdf
CompTox Chemicals Dashboard - Wikipedia, accessed October 14, 2025, https://en.wikipedia.org/wiki/CompTox_Chemicals_Dashboard
Downloadable Computational Toxicology Data | US EPA, accessed October 14, 2025, https://www.epa.gov/comptox-tools/downloadable-computational-toxicology-data
en.wikipedia.org, accessed October 14, 2025, https://en.wikipedia.org/wiki/Model_Context_Protocol
What is Model Context Protocol (MCP)? A guide - Google Cloud, accessed October 14, 2025, https://cloud.google.com/discover/what-is-model-context-protocol
What is the Model Context Protocol (MCP)? - Cloudflare, accessed October 14, 2025, https://www.cloudflare.com/learning/ai/what-is-model-context-protocol-mcp/
Model Context Protocol (MCP): A comprehensive introduction for developers - Stytch, accessed October 14, 2025, https://stytch.com/blog/model-context-protocol-introduction/
Model Context Protocol - GitHub, accessed October 14, 2025, https://github.com/modelcontextprotocol
kmansouri/OPERA: Free and open-source application (command line and GUI) providing QSAR models predictions as well as applicability domain and accuracy assessment for physicochemical properties, environmental fate and toxicological endpoints. ==================>Download the latest compiled - GitHub, accessed October 14, 2025, https://github.com/kmansouri/OPERA
Model Cards for Model Reporting - arXiv, accessed October 14, 2025, https://arxiv.org/pdf/1810.03993
Create a Model Card with Scikit-Learn | Google Cloud Blog, accessed October 14, 2025, https://cloud.google.com/blog/products/ai-machine-learning/create-a-model-card-with-scikit-learn
Model Cards - Kaggle, accessed October 14, 2025, https://www.kaggle.com/code/var0101/model-cards
Google Model Cards, accessed October 14, 2025, https://modelcards.withgoogle.com/
Quantitative Structure-Activity Relationships Project - OECD, accessed October 14, 2025, https://www.oecd.org/en/topics/sub-issues/assessment-of-chemicals/quantitative-structure-activity-relationships-project.html
The Characterisation of (Quantitative) Structure-Activity Relationships - Preliminary Guidance - JRC Publications Repository, accessed October 14, 2025, https://publications.jrc.ec.europa.eu/repository/handle/JRC31241
Gemma model card | Google AI for Developers, accessed October 14, 2025, https://ai.google.dev/gemma/docs/core/model_card
Principles of QSAR models validation: Internal and external | Request PDF - ResearchGate, accessed October 14, 2025, https://www.researchgate.net/publication/215476014_Principles_of_QSAR_models_validation_Internal_and_external
Model Validation Techniques, Explained: A Visual Guide with Code Examples, accessed October 14, 2025, https://medium.com/data-science/model-validation-techniques-explained-a-visual-guide-with-code-examples-eb13bbdc8f88
What is Model Validation and Why is it Important? - GeeksforGeeks, accessed October 14, 2025, https://www.geeksforgeeks.org/machine-learning/what-is-model-validation-and-why-is-it-important/
OPERA models to support regulatory purposes - Environmental Protection Agency (EPA), accessed October 14, 2025, https://www.epa.gov/sites/default/files/2019-04/documents/opera_models_0.pdf
Predicting the Predictability: A Unified Approach to the Applicability Domain Problem of QSAR Models | Journal of Chemical Information and Modeling - ACS Publications, accessed October 14, 2025, https://pubs.acs.org/doi/abs/10.1021/ci9000579
