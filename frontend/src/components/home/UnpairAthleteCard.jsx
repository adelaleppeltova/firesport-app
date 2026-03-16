import Card from "../Card";
import PrimaryButton from "../PrimaryButton";
import { useUnpairAthlete } from "../../hooks/useApi";

function getErrorMessage(error) {
  return error?.response?.data?.detail || "Odpárování se nepodařilo. Zkus to prosím znovu.";
}

export default function UnpairAthleteCard() {
  const unpairMutation = useUnpairAthlete();

  const handleUnpair = async () => {
    if (unpairMutation.isPending) return;

    const confirmed = window.confirm(
      "Opravdu chceš odpárovat závodníka od svého účtu?",
    );

    if (!confirmed) return;

    try {
      await unpairMutation.mutateAsync();
    } catch (error) {
      // Chybu zobrazujeme přímo v kartě.
    }
  };

  return (
    <Card
      title="Propojení účtu"
      className="home-page__footer-card card--home-account"
    >
      <div className="unpair-athlete">
        <p className="unpair-athlete__text">
          Pokud chceš svůj účet propojit s jiným závodníkem, nejdřív zruš
          stávající propojení.
        </p>

        {unpairMutation.isError ? (
          <p className="unpair-athlete__error" role="alert">
            {getErrorMessage(unpairMutation.error)}
          </p>
        ) : null}

        <div className="button-center">
          <PrimaryButton
            onClick={handleUnpair}
            isLoading={unpairMutation.isPending}
            className="unpair-athlete__button"
            disabled={unpairMutation.isPending}
          >
            Odpárovat závodníka
          </PrimaryButton>
        </div>
      </div>
    </Card>
  );
}
