# CST8917 — Assignment 1: Serverless Computing (Critical Analysis)

**Name:** Muhire Rutayisire  
**Student Number:** 41193051
**Date:** February 11, 2026  

---

## Part 1 — Paper Summary

Hellerstein et al. argue that first-generation “serverless” (mostly Functions-as-a-Service, FaaS) is a major usability win for cloud programming, but it sacrifices exactly the things that make cloud computing revolutionary: data-centric performance and efficient distributed coordination. Their “one step forward, two steps back” framing is that FaaS delivers true **autoscaling** and pay-per-use execution of user code (the forward step), yet it simultaneously pushes developers into architectures that are **worse for data movement and distributed systems** than many “serverful” designs (the two backward steps). The authors even warn that this can lock users into proprietary managed services instead of enabling new, open innovation on top of cloud resources. :contentReference[oaicite:0]{index=0} :contentReference[oaicite:1]{index=1}

The paper highlights several concrete limitations typical of FaaS offerings. First, **execution time constraints**: functions have limited lifetimes (the paper uses AWS Lambda’s 15-minute limit as a representative example), and the platform may reuse warm containers but does not guarantee “stickiness” to the same runtime across calls. That forces developers to assume local state won’t reliably persist. :contentReference[oaicite:2]{index=2}

Second, **communication and network limitations**: a single function’s network bandwidth can be far below local storage speeds, and bandwidth per function can *decrease* as concurrency increases because functions may share the same host/network limits. :contentReference[oaicite:3]{index=3} Third, functions are typically **not directly network addressable**, so function-to-function coordination relies on intermediary services (queues/objects/DB), which introduces latency and cost. The paper describes this as “communication through slow storage,” and notes the lack of connection stickiness means state must be written out and reloaded on subsequent calls. :contentReference[oaicite:4]{index=4}

These constraints encourage what the authors call the **“data shipping” anti-pattern**: instead of pushing compute close to data, FaaS commonly pulls data from storage into short-lived compute, repeatedly paying latency/bandwidth overheads. :contentReference[oaicite:5]{index=5} They argue this makes FaaS a poor fit for modern data systems and ML workloads, where performance depends on locality, caching, and high-throughput access. Relatedly, FaaS **stymies distributed computing** because fine-grained protocols (membership, leader election, commit, consistency) need efficient peer communication, which is hard when everything must round-trip through storage. :contentReference[oaicite:6]{index=6} :contentReference[oaicite:7]{index=7} The paper’s measurements reinforce this: communicating via storage is orders of magnitude slower than direct messaging and becomes a bottleneck for coordination-heavy workloads. :contentReference[oaicite:8]{index=8}

Finally, the paper notes limited access to **specialized hardware** (e.g., GPUs/accelerators), which constrains ML and hardware-accelerated data processing innovation. :contentReference[oaicite:9]{index=9}

For future cloud programming, the authors propose directions such as: (1) **fluid code/data placement** to enable “shipping code to data,” (2) **heterogeneous hardware support**, and (3) **long-running, addressable virtual agents** that preserve identity and locality while still being elastically managed. :contentReference[oaicite:10]{index=10}

---

## Part 2 — Azure Durable Functions Deep Dive (100–150 words each)

### 1) Orchestration model
Azure Durable Functions adds a workflow/orchestration layer on top of basic Azure Functions. Instead of writing one function that must finish quickly and remain stateless, you define **orchestrator functions** that coordinate steps, **activity functions** that perform work, and **client functions** that start/monitor orchestrations. This shifts “composition” from ad-hoc chaining via queues/storage into a structured model where the platform schedules and tracks the workflow. Microsoft describes orchestrators as the coordination logic that can call activities, wait for external events, and express control flow (sequence, parallelism, retries) as code. This directly targets the paper’s complaint that first-gen FaaS discourages distributed composition and forces developers into slow, storage-mediated glue for workflows. :contentReference[oaicite:11]{index=11}

### 2) State management
Durable Functions manages state using an **event-sourced execution history**. The orchestrator code can “look” stateful because local variables are reconstructed by replaying the recorded history, and progress is persisted so workflows can resume after restarts. Microsoft explicitly notes that orchestrators use event sourcing, checkpoints, and replay, and that the replay behavior creates constraints (notably, orchestrators must be deterministic). This addresses a core criticism in the paper: vanilla FaaS forces developers to externalize state to storage on every step because functions are ephemeral and non-sticky. Durable Functions doesn’t make the compute instance sticky, but it makes the **workflow state durable** and recoverable without you manually building a state machine. It’s a partial fix: state becomes reliable at the orchestration level, but it’s still mediated by storage/history rather than in-memory locality. :contentReference[oaicite:12]{index=12}

### 3) Execution timeouts
Durable Functions helps with long-running processes by splitting work into resumable steps. An orchestrator can “pause” (for timers/events) and later continue because it replays from history, making it suitable for workflows that take minutes, hours, or days. However, Durable Functions does **not magically remove all time limits**: Microsoft notes that activity, orchestrator, and entity functions are still subject to Azure Functions timeout behavior, and timeouts are treated like failures. The practical takeaway is: Durable Functions avoids the “single execution must run forever” problem by persisting progress and continuing later, but individual activity executions still need to fit within the hosting plan/runtime limits. This mitigates the paper’s “limited lifetimes” concern at the workflow level, but not as a general-purpose model for long-running *compute* inside a single function invocation. :contentReference[oaicite:13]{index=13}

### 4) Communication between functions
In Durable Functions, orchestrators and activities don’t communicate by direct, addressable networking; instead the orchestrator schedules activities and receives their results through the Durable Task runtime, backed by the durable state store (history/events). This improves developer experience versus hand-rolled SQS/S3-style choreography because correlation, retries, and state tracking are built in. But relative to the paper’s critique (“communication through slow storage” and lack of addressability), it is still fundamentally **storage/history mediated** rather than true point-to-point networking between compute agents. The benefit is reliability and simplicity for workflows; the tradeoff is that fine-grained, high-frequency messaging patterns still don’t match the performance profile of direct networking. So Durable Functions reduces the pain of coordination for many business workflows, but it doesn’t fully overturn the architectural limitation the paper highlights. :contentReference[oaicite:14]{index=14}

### 5) Parallel execution (fan-out/fan-in)
Durable Functions has first-class patterns for parallel work, especially **fan-out/fan-in**: the orchestrator starts many activity functions concurrently (“fan-out”), waits for them all to finish, then aggregates results (“fan-in”). Microsoft documents this as a standard Durable pattern for parallelizing independent tasks and then combining outcomes. This directly targets one of the paper’s pain points: first-gen FaaS can do embarrassingly parallel tasks, but struggles to coordinate distributed steps efficiently and reliably. Durable Functions makes this coordination straightforward and fault-tolerant (since the orchestration state is persisted and replayable). Still, the pattern is best when tasks are coarse enough that the orchestration overhead and storage-backed tracking are negligible compared to the work itself—meaning it improves practical distributed coordination, but not the low-latency “fine-grained protocol” world the paper focuses on. :contentReference[oaicite:15]{index=15}

---

## Part 3 — Critical Evaluation

### Limitations that remain unresolved (two examples)

**1) “Data shipping” and locality still dominate.**  
The paper’s biggest architectural critique is that first-gen FaaS ships data to code, repeatedly pulling from remote storage because compute is ephemeral and non-sticky. :contentReference[oaicite:16]{index=16} Durable Functions improves *workflow durability*, not *data locality*. Orchestrators don’t colocate with the data; they coordinate steps whose inputs/outputs typically still live in storage services. Even though replay makes state management easier, it can also reinforce a “history + storage” mindset: the workflow progresses by writing durable events and results rather than keeping hot data close to compute. That means data-intensive analytics, ML training, and systems that depend on cache affinity still face t:contentReference[oaicite:17]{index=17}k: networked I/O and remote storage dominate performance, and scaling compute doesn’t automatically scale bandwidth per worker. :contentReference[oaicite:18]{index=18} In short, Durable Functions makes *stateful orchestration* feasible, but it does not provide the “fluid code and data placement” vision the authors call for. :contentReference[oaicite:19]{index=19}

**2) Lack of addressable, long-running agents and fast inter-agent communication.**  
A second major criticism is that functions are not directly addressable and therefore distributed protocols devolve into storage-mediated communication, which is too slow and expensive for fine-grained coordination. :contentReference[oaicite:20]{index=20}:contentReference[oaicite:21]{index=21}:contentReference[oaicite:22]{index=22} Durable Functions does not turn functions into network-addressable actors with stable identities; instead, it builds reliable coordination on top of an ev:contentReference[oaicite:23]{index=23}at for business workflows (order processing, approvals, retries, human-in-the-loop), but it does not become a substrate for efficient leader election, membership, or low-latency messaging—the exact examples the paper uses to show why storage as a “communication bus” is a non-starter. :contentReference[oaicite:24]{index=24}:contentReference[oaicite:25]{index=25}o:contentReference[oaicite:26]{index=26}inism and replay constraints for orchestrators, which is a very different model from general distributed agents communicating freely. :contentReference[oaicite:27]{index=27}

### Verdict
My verdict is that Azure Durable Functions is meaningful progress for a *subset* of what the authors want—but it is more of a **workaround** than a full solution to the paper’s foundational critiques.

It clearly advances the “cloud programming” experience compared to raw FaaS by giving d:contentReference[oaicite:28]{index=28}tration model with durable state, replay, and built-in patterns like fan-out/fan-in. :contentReference[oaicite:29]{index=29} This directly reduces the complexity of building reliable, multi-step workflows and mitigates the “stateless, ephemeral” pain by moving state handling into the platform (so you don’t manually write a state machine).

However, Durable Functions does not deliver the authors’ deeper architectural asks: it doesn’t provide fluid placement to reduce data shipping, and it doesn’t create long-running, addressable virtual agents with near-network-speed communication. :contentReference[oaicite:30]{index=30} Instead, it makes storage-backed coordination easier to use. That’s extremely valuable in practice (especially for orchestration-heavy apps), but it still leaves data-centric and fine-grained distributed computing workloads constrained by the same locality and communication fundamentals the paper critiques. In other words: Durable Functions improves what you can build *despite* first-gen serverless constraints, but it doesn’t fully redefine the constraints in the direction the authors propose.

---

## References

- Hellerstein, J. M., et al. (2019). *Serverless Computing: One Step Forward, Two Steps Back.* CIDR 2019. (Provided PDF in assignment handout.) :contentReference[oaicite:31]{index=31}  
- Microsoft Learn — Durable :contentReference[oaicite:32]{index=32}earn.microsoft.com/azure/azure-functions/durable/durable-functions-overview :contentReference[oaicite:33]{index=33}  
- Microsoft Learn — Durable orchestrations (orchestrator concepts). https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-orchestrations :contentReference[oaicite:34]{index=34}  
- Microsoft Learn — Orchestrator code constraints (event sourcing, replay, determinism). https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-code-constraints :contentReference[oaicite:35]{index=35}  
- Microsoft Learn — Performance and scale (timeouts behavior). https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-perf-and-scale :contentReference[oaicite:36]{index=36}  
- Micr:contentReference[oaicite:37]{index=37} scenario. https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-cloud-backup :contentReference[oaicite:38]{index=38}  

---

## AI Disclosure Statement

I used ChatGPT to help (1) draft an initial summary of the paper’s main arguments and limitations, (2) structure the Durable Functions analysis by topic, and (3) refine wording for clarity. I reviewed the paper myself and verified Durable Functions claims using Microsoft Learn documentation (cited above).
