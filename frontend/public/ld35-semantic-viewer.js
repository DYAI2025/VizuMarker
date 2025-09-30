/**
 * Enhanced LD3.5 semantic viewer for sentence-level highlighting
 * Shows composed markers with contextual spans instead of just word-level highlights
 */

class LD35SemanticViewer {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    this.options = {
      showMetadata: true,
      highlightSentences: true,
      showFamilyColors: true,
      showScores: true,
      expandable: true,
      ...options,
    };

    this.familyColors = {
      SEM: "#ff6b6b", // Red for semantic patterns
      CLU: "#4ecdc4", // Teal for clustering patterns
      ATO: "#45b7d1", // Blue for atomic patterns
      MEMA: "#96ceb4", // Green for MEMA patterns
      DEESC: "#ffeaa7", // Yellow for de-escalation
    };

    this.init();
  }

  init() {
    if (!this.container) {
      console.error("LD35SemanticViewer: Container not found");
      return;
    }

    this.container.classList.add("ld35-viewer");
    this.addStyles();
  }

  addStyles() {
    if (document.getElementById("ld35-viewer-styles")) return;

    const style = document.createElement("style");
    style.id = "ld35-viewer-styles";
    style.textContent = `
            .ld35-viewer {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                line-height: 1.6;
                max-width: 100%;
            }
            
            .ld35-text {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 8px;
                margin: 10px 0;
                position: relative;
            }
            
            .ld35-annotation {
                position: relative;
                border-radius: 3px;
                padding: 2px 4px;
                margin: 0 1px;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            
            .ld35-annotation:hover {
                transform: translateY(-1px);
                box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            }
            
            .ld35-annotation.sem { background-color: rgba(255, 107, 107, 0.3); border-left: 3px solid #ff6b6b; }
            .ld35-annotation.clu { background-color: rgba(78, 205, 196, 0.3); border-left: 3px solid #4ecdc4; }
            .ld35-annotation.ato { background-color: rgba(69, 183, 209, 0.3); border-left: 3px solid #45b7d1; }
            .ld35-annotation.mema { background-color: rgba(150, 206, 180, 0.3); border-left: 3px solid #96ceb4; }
            .ld35-annotation.deesc { background-color: rgba(255, 234, 167, 0.3); border-left: 3px solid #ffeaa7; }
            
            .ld35-score {
                font-size: 0.7em;
                background: rgba(0,0,0,0.7);
                color: white;
                padding: 1px 4px;
                border-radius: 2px;
                margin-left: 4px;
                vertical-align: super;
            }
            
            .ld35-metadata {
                background: white;
                border: 1px solid #e9ecef;
                border-radius: 6px;
                padding: 15px;
                margin: 10px 0;
                font-size: 0.9em;
            }
            
            .ld35-stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
                gap: 10px;
                margin: 10px 0;
            }
            
            .ld35-stat {
                text-align: center;
                padding: 8px;
                background: #f8f9fa;
                border-radius: 4px;
            }
            
            .ld35-stat-value {
                font-size: 1.2em;
                font-weight: bold;
                color: #495057;
            }
            
            .ld35-stat-label {
                font-size: 0.8em;
                color: #6c757d;
                margin-top: 2px;
            }
            
            .ld35-tooltip {
                position: absolute;
                background: rgba(0,0,0,0.9);
                color: white;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 0.8em;
                pointer-events: none;
                z-index: 1000;
                max-width: 250px;
                line-height: 1.4;
            }
            
            .ld35-family-legend {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin: 10px 0;
                padding: 10px;
                background: #f8f9fa;
                border-radius: 6px;
            }
            
            .ld35-family-item {
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 0.85em;
            }
            
            .ld35-family-color {
                width: 12px;
                height: 12px;
                border-radius: 2px;
            }
        `;
    document.head.appendChild(style);
  }

  render(analysisResult) {
    if (!analysisResult) return;

    const { text, annotations, metadata } = analysisResult;

    this.container.innerHTML = "";

    // Render metadata if available
    if (this.options.showMetadata && metadata) {
      this.renderMetadata(metadata);
    }

    // Render family legend
    if (this.options.showFamilyColors) {
      this.renderFamilyLegend(annotations);
    }

    // Render annotated text
    this.renderAnnotatedText(text, annotations);

    // Add interaction handlers
    this.addInteractionHandlers();
  }

  renderMetadata(metadata) {
    const metadataDiv = document.createElement("div");
    metadataDiv.className = "ld35-metadata";

    const stats = document.createElement("div");
    stats.className = "ld35-stats";

    const statsData = [
      { label: "Atomic", value: metadata.atomic_count || 0 },
      { label: "Composed", value: metadata.composed_count || 0 },
      { label: "Final", value: metadata.final_count || 0 },
    ];

    statsData.forEach((stat) => {
      const statDiv = document.createElement("div");
      statDiv.className = "ld35-stat";
      statDiv.innerHTML = `
                <div class="ld35-stat-value">${stat.value}</div>
                <div class="ld35-stat-label">${stat.label}</div>
            `;
      stats.appendChild(statDiv);
    });

    metadataDiv.appendChild(stats);
    this.container.appendChild(metadataDiv);
  }

  renderFamilyLegend(annotations) {
    const families = [...new Set(annotations.map((a) => a.family))];
    if (families.length === 0) return;

    const legend = document.createElement("div");
    legend.className = "ld35-family-legend";

    families.forEach((family) => {
      const item = document.createElement("div");
      item.className = "ld35-family-item";

      const color = document.createElement("div");
      color.className = "ld35-family-color";
      color.style.backgroundColor = this.familyColors[family] || "#gray";

      const label = document.createElement("span");
      label.textContent = family;

      item.appendChild(color);
      item.appendChild(label);
      legend.appendChild(item);
    });

    this.container.appendChild(legend);
  }

  renderAnnotatedText(text, annotations) {
    const textDiv = document.createElement("div");
    textDiv.className = "ld35-text";

    // Sort annotations by start position
    const sortedAnnotations = [...annotations].sort(
      (a, b) => a.start - b.start || b.end - a.end
    );

    // Create annotation events for rendering
    const events = [];
    sortedAnnotations.forEach((ann, index) => {
      events.push({ pos: ann.start, type: "open", annotation: ann, index });
      events.push({ pos: ann.end, type: "close", annotation: ann, index });
    });

    events.sort((a, b) => a.pos - b.pos || (a.type === "close" ? -1 : 1));

    let html = "";
    let pos = 0;
    const stack = [];

    events.forEach((event) => {
      // Add text before this position
      if (event.pos > pos) {
        html += this.escapeHtml(text.slice(pos, event.pos));
        pos = event.pos;
      }

      if (event.type === "open") {
        const ann = event.annotation;
        const familyClass = ann.family.toLowerCase();
        const scoreHtml = this.options.showScores
          ? `<span class="ld35-score">${(ann.score || 0).toFixed(2)}</span>`
          : "";

        html += `<span class="ld35-annotation ${familyClass}" 
                        data-marker-id="${ann.marker_id}" 
                        data-family="${ann.family}"
                        data-score="${ann.score || 0}"
                        data-start="${ann.start}"
                        data-end="${ann.end}"
                        title="${ann.marker_id}: ${(ann.score || 0).toFixed(
          2
        )}">`;
        stack.push(event.annotation);
      } else {
        html +=
          this.options.showScores && stack.length === 1
            ? `<span class="ld35-score">${(event.annotation.score || 0).toFixed(
                2
              )}</span></span>`
            : "</span>";
        stack.pop();
      }
    });

    // Add remaining text
    if (pos < text.length) {
      html += this.escapeHtml(text.slice(pos));
    }

    textDiv.innerHTML = html;
    this.container.appendChild(textDiv);
  }

  addInteractionHandlers() {
    // Tooltip handling
    let tooltip = null;

    this.container.addEventListener(
      "mouseenter",
      (e) => {
        if (!e.target.classList.contains("ld35-annotation")) return;

        const markerId = e.target.dataset.markerId;
        const family = e.target.dataset.family;
        const score = parseFloat(e.target.dataset.score);
        const start = parseInt(e.target.dataset.start);
        const end = parseInt(e.target.dataset.end);

        tooltip = document.createElement("div");
        tooltip.className = "ld35-tooltip";
        tooltip.innerHTML = `
                <strong>${markerId}</strong><br>
                Family: ${family}<br>
                Score: ${score.toFixed(3)}<br>
                Span: ${start}-${end} (${end - start} chars)
            `;

        document.body.appendChild(tooltip);

        const updateTooltipPosition = (event) => {
          tooltip.style.left = event.pageX + 10 + "px";
          tooltip.style.top = event.pageY - 10 + "px";
        };

        updateTooltipPosition(e);
        e.target.addEventListener("mousemove", updateTooltipPosition);
      },
      true
    );

    this.container.addEventListener(
      "mouseleave",
      (e) => {
        if (!e.target.classList.contains("ld35-annotation")) return;

        if (tooltip) {
          tooltip.remove();
          tooltip = null;
        }
      },
      true
    );

    // Click handling for detailed info
    this.container.addEventListener("click", (e) => {
      if (!e.target.classList.contains("ld35-annotation")) return;

      const markerId = e.target.dataset.markerId;
      console.log("Clicked annotation:", {
        markerId,
        family: e.target.dataset.family,
        score: e.target.dataset.score,
        start: e.target.dataset.start,
        end: e.target.dataset.end,
      });

      // Emit custom event for integration
      this.container.dispatchEvent(
        new CustomEvent("annotationClick", {
          detail: {
            markerId,
            family: e.target.dataset.family,
            score: parseFloat(e.target.dataset.score),
            start: parseInt(e.target.dataset.start),
            end: parseInt(e.target.dataset.end),
            element: e.target,
          },
        })
      );
    });
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // Public methods for integration
  async renderFromApi(
    text,
    apiEndpoint = "/api/v1/annotation/annotate-semantic"
  ) {
    try {
      const response = await fetch(apiEndpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const result = await response.json();
      this.render(result);
      return result;
    } catch (error) {
      console.error("Error fetching analysis:", error);
      this.container.innerHTML = `<div style="color: red; padding: 20px;">Error: ${error.message}</div>`;
      throw error;
    }
  }

  clear() {
    this.container.innerHTML = "";
  }

  export() {
    return {
      html: this.container.innerHTML,
      styles: document.getElementById("ld35-viewer-styles")?.textContent,
    };
  }
}

// Global helper function for quick setup
window.LD35SemanticViewer = LD35SemanticViewer;

// Example usage:
// const viewer = new LD35SemanticViewer('viewer-container');
// viewer.renderFromApi('Your text to analyze here');
