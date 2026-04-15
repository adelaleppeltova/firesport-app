import Card from "../Card";
import PrimaryButton from "../PrimaryButton";
import { useUnpairAthlete } from "../../hooks/useApi";

function getErrorMessage(error) {
  return error?.response?.data?.detail || "Odpárování se nezdařilo. Zkuste to znovu.";
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
      return;
    }
  };

  return (
    <Card
      title="Propojení účtu"
      className="home-page__footer-card card--home-account"
    >
      <div className="unpair-athlete">
        <p className="unpair-athlete__text">
          Chcete-li účet propojit s jiným závodníkem, nejdřív zrušte současné
          propojení.
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
