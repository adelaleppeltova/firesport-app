import { useState } from "react";
import Card from "../Card";
import PairAthleteDialog from "./PairAthleteDialog";
import PrimaryButton from "../PrimaryButton";

export default function PairAthleteCard() {
  const [showPairDialog, setShowPairDialog] = useState(false);

  return (
    <>
      <Card title="Spáruj svůj účet s atletem">
        <div className="pair-athlete">
          <p className="pair-athlete__text">
            Spáruj svůj uživatelský účet s atletem, aby sis mohl prohlížet své
            výsledky a statistiky.
          </p>
          <div className="button-center">
            <PrimaryButton onClick={() => setShowPairDialog(true)}>
              Spárovat atleta
            </PrimaryButton>
          </div>
        </div>
      </Card>
      {showPairDialog && (
        <PairAthleteDialog onClose={() => setShowPairDialog(false)} />
      )}
    </>
  );
}
