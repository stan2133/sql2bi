const yearNode = document.getElementById("year");
if (yearNode) {
  yearNode.textContent = String(new Date().getFullYear());
}

const copyButtons = document.querySelectorAll("[data-copy-target]");
copyButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    const targetId = button.getAttribute("data-copy-target");
    const source = targetId ? document.getElementById(targetId) : null;
    const text = source ? source.textContent || "" : "";

    if (!text.trim()) {
      return;
    }

    try {
      await navigator.clipboard.writeText(text);
      const original = button.textContent;
      button.textContent = "已复制";
      window.setTimeout(() => {
        button.textContent = original || "复制";
      }, 1200);
    } catch (error) {
      console.error("Copy failed:", error);
    }
  });
});
