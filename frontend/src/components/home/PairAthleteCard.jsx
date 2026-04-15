import { useState } from "react";
import Card from "../Card";
import PairAthleteDialog from "./PairAthleteDialog";
import PrimaryButton from "../PrimaryButton";

export default function PairAthleteCard() {
  const [showPairDialog, setShowPairDialog] = useState(false);

  return (
    <>
      <Card title="Propoj účet se závodníkem" className="card--home-account">
        <div className="pair-athlete">
          <div className="button-center">
            <PrimaryButton onClick={() => setShowPairDialog(true)}>
              Vybrat závodníka
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
