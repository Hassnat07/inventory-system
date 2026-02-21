document.addEventListener("DOMContentLoaded", () => {
    loadLensesForSelect();
});

// Function to load lenses into the dropdown when the page or modal opens
function loadLensesForSelect() {
    fetch("/inventory/stock") // Adjust this route to wherever you fetch lens list
    .then(res => res.json())
    .then(data => {
        const select = document.getElementById("lensSelect");
        select.innerHTML = '<option value="">Choose registered lens...</option>';
        
        data.forEach(lens => {
            const opt = document.createElement("option");
            opt.value = lens.id; // Ensure your backend returns the Lens ID
            opt.textContent = lens.name;
            select.appendChild(opt);
        });
    });
}

// Simplified Add Lens (Name Only)
function addLens() {
    const name = document.getElementById("lensName").value;
    if (!name) return alert("Please enter the lens name.");

    fetch("/inventory/add-lens", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert("Lens registered successfully.");
            location.reload();
        }
    });
}

// Detailed Stock Entry (Lens + Power + Qty)
function stockIn() {
    const lensId = document.getElementById("lensSelect").value;
    const power = document.getElementById("stockPower").value;
    const qty = document.getElementById("quantity").value;

    if (!lensId || !qty) return alert("Please select a lens and quantity.");

    fetch("/inventory/stock-in", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            lens_id: lensId,
            power: power, // Send power to backend
            quantity: parseInt(qty),
            supplier: document.getElementById("supplier").value,
            purchase_date: new Date().toISOString().split('T')[0]
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert("Stock updated successfully.");
            location.reload();
        }
    });
}

// Initialize the dropdown when page loads
document.addEventListener("DOMContentLoaded", loadLensesForSelect);