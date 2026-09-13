# Emissions Extension

This extension calculates and displays gas turbine emissions, specifically the major greenhouse gases and pollutants (NOx, CO, and CO2). 

## Design Plan

### 1. Combustion Classification & Correlation
To classify the combustion state as **Lean Burn**, **Balanced (Stoichiometric)**, or **Rich Burn**, we calculate the **Equivalence Ratio (Φ)**. This is a correlation between the actual fuel added versus the ideal stoichiometric fuel needed for the given air mass flow.

*   **Φ < 1.0**: Lean Burn (excess air — typical for gas turbines)
*   **Φ == 1.0**: Balanced (perfect mixture)
*   **Φ > 1.0**: Rich Burn (excess fuel — usually only seen in afterburners)

### 2. Emissions Calculation
Cantera natively simulates the combustion chemistry at the provided temperature and pressure, inherently computing the equilibrium mole fractions for the combustion products.

We will extract the mole fractions for **NOx** (NO + NO2), **CO**, and **CO2** from Cantera's post-combustion gas object (Station 4). Then, we will apply the Emission Index (EI) formula using the Fuel-to-Air Ratio (FAR) correlation to get grams of pollutant per kilogram of fuel:

`EI = (Mole Fraction * Molecular Weight) / (FAR * Mixture Molecular Weight) * 1000`

### 3. Backend Data Structure
The emissions data will be kept localized to the combustor exit (Station 4). The modified JSON response from the API will structure the Station 4 data block as follows:

```json
{
  "name": "Station 4 - Combustor Exit",
  "T": 1560.5,
  "P": 2850000.0,
  "combustion_metrics": {
    "fuel_air_ratio": 0.024,
    "equivalence_ratio": 0.35,
    "burn_state": "Lean Burn",
    "emissions_EI": {
      "NOx": 12.4,
      "CO": 1.2,
      "CO2": 3150.0
    }
  }
}
```

### 4. Frontend Matrix
A lightweight, non-intrusive matrix (or sub-table) will be added to the frontend. It will be nested directly under the Station 4 row in the existing results table, displaying the classification and the EI values without cluttering the primary performance metrics.
