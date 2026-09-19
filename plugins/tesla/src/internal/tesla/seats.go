package tesla

import "github.com/teslamotors/vehicle-command/pkg/vehicle"

// A seat pairs the name a caller uses with the SDK constant it stands for.
type seat struct {
	name     string
	position vehicle.SeatPosition
}

// heatableSeats are the nine positions the seat heater can address: exactly
// the ones SeatPosition.addToHeaterAction maps to a protobuf seat
// (pkg/vehicle/climate.go:110-133), and the same set the command proxy offers
// (pkg/proxy/command.go:25-35). The order here is the order the schema
// advertises: the three rear seats, then the two Model S backrests.
var heatableSeats = []seat{
	{"front_left", vehicle.SeatFrontLeft},
	{"front_right", vehicle.SeatFrontRight},
	{"rear_left", vehicle.SeatSecondRowLeft},
	{"rear_center", vehicle.SeatSecondRowCenter},
	{"rear_right", vehicle.SeatSecondRowRight},
	{"rear_left_back", vehicle.SeatSecondRowLeftBack},
	{"rear_right_back", vehicle.SeatSecondRowRightBack},
	{"third_row_left", vehicle.SeatThirdRowLeft},
	{"third_row_right", vehicle.SeatThirdRowRight},
}

// frontSeats are the only positions seat cooling and automatic seat climate
// can reach. SetSeatCooler refuses anything else outright
// (pkg/vehicle/climate.go:13-20), and AutoSeatAndClimate silently drops it:
// its lookup holds only the front two, so an unmapped position leaves the
// request with an empty seat list (climate.go:65-75). The protobuf agrees —
// AutoSeatPosition has no rear values at all
// (protobuf/carserver/car_server.pb.go:225-229) — so advertising a rear seat
// on those two tools would be advertising a command that does nothing.
var frontSeats = []seat{
	{"front_left", vehicle.SeatFrontLeft},
	{"front_right", vehicle.SeatFrontRight},
}

// seatNames lists a table's names in the order it declares them, for the
// schema's enum and for the refusal that names the alternatives.
func seatNames(seats []seat) []string {
	names := make([]string, 0, len(seats))
	for _, candidate := range seats {
		names = append(names, candidate.name)
	}
	return names
}

// seatPosition returns the SDK constant for an advertised seat name.
//
// It is total by construction: Validate has already refused every name outside
// the same table, so a miss here means the table and the validator were built
// from different lists, which is a fault in this package rather than a bad
// call. Fail loudly rather than heat whatever SeatUnknown resolves to.
func seatPosition(seats []seat, name string) vehicle.SeatPosition {
	for _, candidate := range seats {
		if candidate.name == name {
			return candidate.position
		}
	}
	panic("tesla: " + name + " is not a seat this table maps")
}

// levelFor turns the advertised 0..3 into the SDK's Level, whose constants
// LevelOff, LevelLow, LevelMed and LevelHigh are exactly 0..3
// (pkg/vehicle/climate.go:135-142).
func levelFor(level int) vehicle.Level {
	return vehicle.Level(level)
}
